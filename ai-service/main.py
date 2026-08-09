# FastAPI 入口，暴露 3 个 HTTP 端点：

import json
import os
os.environ.pop("SSLKEYLOGFILE", None)  # 消除 Wireshark SSL 抓包的环境变量干扰

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from schemas import ChatRequest, ChatResponse
from agent import process_message, stream_agent
from trace import TraceStore
from db import load_products  # 架构 A：Python 直连 MySQL 加载商品

app = FastAPI(title="AI 鞋类推荐助手", version="3.0")

# CORS 中间件
# 注意：当前架构下浏览器只与 Java 后端（同源 /api/...）通信，
# Python 由 Java 服务端调用（AiAgentClient），所以浏览器实际不会触发这里。
# 但若以后改为浏览器直连 Python，必须显式列出来源——
# allow_credentials=True 与 allow_origins=["*"] 同时出现是非法组合
# （浏览器会直接拒绝），故不允许用 "*"。
_CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080")
    .split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/health")
def health():
    """健康检查"""
    return {"status": "ok"}


@app.post("/api/ai/agent/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Agent 对话入口（非流式，保留兼容）"""
    # 架构 A：优先用请求传入的商品（兼容旧路径），为空则 Python 直连 MySQL 加载
    products = [p.model_dump() for p in req.products] if req.products else load_products()

    result = process_message(
        conversation_id=req.conversation_id,
        user_message=req.message,
        products=products,
        # 用户画像：Java 端传入，为空也无妨
        user_context=req.user_context,
        # 对话历史：Java 端从 MySQL 查出后传入，用于恢复 Python Agent 记忆
        history=req.history,
    )

    return ChatResponse(
        conversation_id=result["conversation_id"],
        reply=result["reply"],
        action=result["action"],
        results=result["results"],
        # 追问建议：让用户点一下就能继续对话，降低输入门槛
        followUps=result.get("followUps"),
    )


@app.post("/api/ai/agent/chat/stream")
async def chat_stream(req: ChatRequest):
    """Agent 流式对话入口 —— 返回 SSE（Server-Sent Events）流"""
    # 架构 A：优先用请求传入的商品（兼容旧路径），为空则 Python 直连 MySQL 加载
    products = [p.model_dump() for p in req.products] if req.products else load_products()

    # StreamingResponse 配合异步生成器，每个 yield 立即推送到前端
    return StreamingResponse(
        stream_agent(
            conversation_id=req.conversation_id,
            user_message=req.message,
            products=products,
            # 用户画像用于个性化推荐
            user_context=req.user_context,
            # 对话历史：Java 端从 MySQL 查出后传入，用于恢复记忆
            history=req.history,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",      # 禁止浏览器缓存 SSE 流
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",        # 禁用 nginx 代理缓冲
        },
    )


# ===== 可观测性：统计接口 =====
# 数据来源：trace.py 写入的 SQLite traces.db
# 这些接口被前端看板调用，也可以直接用 curl 查


@app.get("/admin/stats")
def admin_stats(days: int = Query(default=7, ge=1, le=90, description="统计天数")):
    """返回指定天数内的聚合统计：总览 + 延迟分位数 + 每小时请求 + 工具分布。
    为什么一个接口返回全部？—— 避免前端多次请求，SQLite 查询很快。"""
    sql_time = f"datetime('now', '-{days} days')"

    # 1. 总览
    overview = TraceStore.query(f"""
        SELECT
            COUNT(*) AS total_requests,
            ROUND(AVG(duration_ms), 1) AS avg_duration_ms,
            ROUND(AVG(first_token_ms), 1) AS avg_first_token_ms,
            SUM(tokens_input) AS total_tokens_in,
            SUM(tokens_output) AS total_tokens_out,
            ROUND(SUM(tokens_input + tokens_output) * 0.000002, 4) AS estimated_cost_rmb,
            ROUND(COUNT(CASE WHEN error IS NOT NULL THEN 1 END) * 100.0 / MAX(COUNT(*), 1), 1) AS error_rate
        FROM agent_traces
        WHERE timestamp >= {sql_time}
    """)

    # 2. 延迟分位数（P50, P95, P99）
    latency_query = f"""
        SELECT duration_ms FROM agent_traces
        WHERE timestamp >= {sql_time} AND duration_ms > 0
        ORDER BY duration_ms
    """
    latencies = [r["duration_ms"] for r in TraceStore.query(latency_query)]
    p50 = _percentile(latencies, 50)
    p95 = _percentile(latencies, 95)
    p99 = _percentile(latencies, 99)

    # 3. 每小时请求量（最近 24 小时完整数据 + 7 天趋势）
    hourly = TraceStore.query(f"""
        SELECT
            strftime('%Y-%m-%dT%H:00', timestamp) AS hour,
            COUNT(*) AS count,
            ROUND(AVG(duration_ms), 1) AS avg_duration_ms
        FROM agent_traces
        WHERE timestamp >= datetime('now', '-{min(days, 7)} days')
        GROUP BY hour
        ORDER BY hour ASC
    """)

    # 4. 工具调用统计
    tools_raw = TraceStore.query(f"""
        SELECT tool_calls FROM agent_traces
        WHERE timestamp >= {sql_time} AND tool_calls != '[]'
    """)
    tool_stats = _aggregate_tools(tools_raw)

    # 5. 每日 token 趋势
    daily_tokens = TraceStore.query(f"""
        SELECT
            date(timestamp) AS day,
            SUM(tokens_input) AS tokens_in,
            SUM(tokens_output) AS tokens_out,
            COUNT(*) AS requests
        FROM agent_traces
        WHERE timestamp >= {sql_time}
        GROUP BY day
        ORDER BY day ASC
    """)

    return {
        "overview": overview[0] if overview else {},
        "latency": {"p50_ms": p50, "p95_ms": p95, "p99_ms": p99},
        "hourly": hourly,
        "tools": tool_stats,
        "daily_tokens": daily_tokens,
    }


@app.get("/admin/stats/recent")
def admin_stats_recent(limit: int = Query(default=50, ge=1, le=200)):
    """返回最近 N 条 trace 记录（给看板的明细表格用）"""
    rows = TraceStore.query("""
        SELECT trace_id, timestamp, duration_ms, first_token_ms,
               tool_calls, tokens_input, tokens_output, error, conversation_id
        FROM agent_traces
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    # tool_calls 是 JSON 字符串，反序列化方便前端用
    for r in rows:
        try:
            r["tool_calls"] = json.loads(r["tool_calls"])
        except Exception:
            r["tool_calls"] = []
    return {"traces": rows}


# —— 工具函数 ——

def _percentile(sorted_data: list[float], p: int) -> float:
    """计算百分位数（线性插值）。sorted_data 必须已排序。"""
    if not sorted_data:
        return 0
    k = (len(sorted_data) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(sorted_data) - 1)
    frac = k - lo
    return round(sorted_data[lo] * (1 - frac) + sorted_data[hi] * frac, 1)


def _aggregate_tools(tools_raw: list[dict]) -> list[dict]:
    """从多条 trace 的 tool_calls JSON 中聚合出工具调用频次和平均耗时"""
    tool_map: dict[str, dict] = {}
    for row in tools_raw:
        try:
            calls = json.loads(row["tool_calls"])
        except Exception:
            continue
        for c in calls:
            name = c.get("name", "unknown")
            dur = c.get("duration_ms", 0)
            if name not in tool_map:
                tool_map[name] = {"name": name, "count": 0, "total_ms": 0.0}
            tool_map[name]["count"] += 1
            tool_map[name]["total_ms"] += dur

    result = []
    for v in tool_map.values():
        v["avg_ms"] = round(v["total_ms"] / v["count"], 1) if v["count"] > 0 else 0
        del v["total_ms"]
        result.append(v)
    result.sort(key=lambda x: x["count"], reverse=True)
    return result


if __name__ == "__main__":
    import uvicorn
    print("AI Agent 服务启动：http://localhost:5000/docs")
    uvicorn.run(app, host="127.0.0.1", port=5000)
