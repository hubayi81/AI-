"""
Agent 批量测试工具 —— 跑一组典型 query，从 traces.db 输出汇总指标。
启动 Agent 服务后运行：python benchmark.py
"""
import os
os.environ.pop("SSLKEYLOGFILE", None)

import json
import time
import sqlite3
import requests

# ===== 1. 测试数据 =====
# 从 init.sql 中选取的真实商品
PRODUCTS = [
    {"id": 1, "name": "Air Max 270", "brand": "Nike", "category": "运动鞋", "gender": "male", "price": 899, "description": "经典气垫运动鞋，舒适缓震", "color": "黑色", "sizeRange": "39-45", "stock": 100},
    {"id": 2, "name": "Ultraboost 23", "brand": "Adidas", "category": "跑鞋", "gender": "male", "price": 1099, "description": "Boost中底科技，能量反馈跑鞋", "color": "白色", "sizeRange": "39-44", "stock": 80},
    {"id": 3, "name": "Chuck Taylor All Star", "brand": "Converse", "category": "帆布鞋", "gender": "unisex", "price": 499, "description": "经典帆布鞋，百搭单品", "color": "米白", "sizeRange": "35-43", "stock": 150},
    {"id": 4, "name": "Old Skool", "brand": "Vans", "category": "板鞋", "gender": "unisex", "price": 569, "description": "标志性侧边条纹，街头风格", "color": "黑白", "sizeRange": "35-44", "stock": 120},
    {"id": 5, "name": "Air Jordan 1 Low", "brand": "Nike", "category": "篮球鞋", "gender": "male", "price": 999, "description": "飞人经典低帮款，复古篮球鞋", "color": "红黑", "sizeRange": "39-45", "stock": 60},
    {"id": 6, "name": "Cloudmonster", "brand": "On", "category": "跑鞋", "gender": "female", "price": 1299, "description": "瑞士On跑鞋，极致缓震", "color": "白紫", "sizeRange": "35-40", "stock": 40},
    {"id": 7, "name": "Gazelle Bold", "brand": "Adidas", "category": "休闲鞋", "gender": "female", "price": 799, "description": "厚底增高休闲鞋，时尚复古", "color": "粉色", "sizeRange": "35-39", "stock": 90},
    {"id": 8, "name": "Classic Clog", "brand": "Crocs", "category": "休闲鞋", "gender": "unisex", "price": 399, "description": "轻便洞洞鞋，清凉一夏", "color": "白色", "sizeRange": "36-45", "stock": 200},
    {"id": 9, "name": "Dunk Low", "brand": "Nike", "category": "运动鞋", "gender": "female", "price": 749, "description": "复古Dunk系列，配色清新百搭", "color": "浅蓝", "sizeRange": "35.5-40", "stock": 70},
    {"id": 10, "name": "Gel-Kayano 30", "brand": "Asics", "category": "跑鞋", "gender": "male", "price": 1190, "description": "亚瑟士稳定支撑跑鞋，长跑利器", "color": "深蓝", "sizeRange": "39-45", "stock": 50},
]

# 测试 query 覆盖不同意图：搜索推荐、穿搭分析、对比、知识问答
TEST_QUERIES = [
    # 搜索推荐类（最核心场景）
    ("纯搜索", "男生跑步膝盖不好预算500以内"),
    ("搜索+追问条件", "脚宽的跑鞋"),
    ("搜索+多条件", "夏天穿轻便透气便宜的女鞋"),
    # 穿搭分析类
    ("穿搭推荐", "今天穿白T恤牛仔裤，配什么鞋好"),
    ("穿搭+场合", "去约会穿的鞋，文艺一点的风格"),
    # 对比类
    ("商品对比", "帮我对比一下Air Max 270和Ultraboost 23"),
    # 知识类（调用 knowledge_base）
    ("专业知识", "扁平足该怎么选跑鞋"),
    ("材质辨别", "Boost和GEL缓震科技有什么区别"),
    # 边界场景
    ("模糊需求", "帮我推荐一双鞋"),
    ("无匹配", "登山攀岩的鞋"),
]

AGENT_URL = "http://127.0.0.1:5000/api/ai/agent/chat"
TRACE_DB = os.path.join(os.path.dirname(__file__), "traces.db")


def run_test(label, query):
    """发送一次请求，返回耗时"""
    start = time.time()
    try:
        r = requests.post(
            AGENT_URL,
            json={"message": query, "products": PRODUCTS},
            timeout=60,
        )
        elapsed = time.time() - start
        data = r.json()
        action = data.get("action", "?")
        results_count = len(data.get("results") or [])
        followups = len(data.get("followUps") or [])
        return {"ok": True, "elapsed": elapsed, "action": action, "results_count": results_count, "followups": followups}
    except Exception as e:
        return {"ok": False, "elapsed": time.time() - start, "error": str(e)}


def read_traces():
    """读取 traces.db 中最近的所有记录"""
    if not os.path.exists(TRACE_DB):
        return []
    conn = sqlite3.connect(TRACE_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM agent_traces ORDER BY timestamp DESC LIMIT ?",
        (len(TEST_QUERIES) * 2,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ===== 主流程 =====
if __name__ == "__main__":
    print("=" * 60)
    print("Agent 批量测试")
    print(f"测试 query 数: {len(TEST_QUERIES)}")
    print(f"商品库数量: {len(PRODUCTS)}")
    print("=" * 60)

    results = []
    for label, query in TEST_QUERIES:
        print(f"\n[{label}] {query}")
        r = run_test(label, query)
        results.append({**r, "label": label, "query": query})
        if r["ok"]:
            print(f"  ✓ 耗时 {r['elapsed']:.1f}s | action={r['action']} | 推荐数={r['results_count']} | 追问={r['followups']}")
        else:
            print(f"  ✗ 失败: {r['error']}")

    # 汇总
    ok_results = [r for r in results if r["ok"]]
    if not ok_results:
        print("\n所有请求失败，请确认 Agent 服务已启动")
        exit(1)

    print("\n" + "=" * 60)
    print("📊 响应时间汇总")
    print("=" * 60)
    all_times = [r["elapsed"] for r in ok_results]
    all_times.sort()
    print(f"  平均: {sum(all_times) / len(all_times):.1f}s")
    print(f"  最快: {all_times[0]:.1f}s")
    print(f"  最慢: {all_times[-1]:.1f}s")
    print(f"  中位数: {all_times[len(all_times) // 2]:.1f}s")

    # 按意图分组
    print("\n📊 按场景分组")
    groups = {}
    for r in ok_results:
        key = r["action"]
        if key not in groups:
            groups[key] = []
        groups[key].append(r["elapsed"])
    for k, v in groups.items():
        print(f"  {k}: 平均 {sum(v)/len(v):.1f}s ({len(v)} 条)")

    # 从 traces.db 读取更细粒度的数据
    traces = read_traces()
    if traces:
        print("\n📊 工具调用分析（来自 traces.db）")
        tool_stats = {}
        for t in traces:
            tool_calls = t.get("tool_calls", "[]")
            if isinstance(tool_calls, str):
                tool_calls = json.loads(tool_calls)
            for tc in tool_calls:
                name = tc["name"]
                if name not in tool_stats:
                    tool_stats[name] = []
                tool_stats[name].append(tc["duration_ms"])

        for name, durations in tool_stats.items():
            avg = sum(durations) / len(durations)
            print(f"  {name}: 平均 {avg:.0f}ms, 调用 {len(durations)} 次")

        # 调用次数分布
        tool_call_counts = []
        for t in traces:
            tool_calls = t.get("tool_calls", "[]")
            if isinstance(tool_calls, str):
                tool_calls = json.loads(tool_calls)
            tool_call_counts.append(len(tool_calls))
        if tool_call_counts:
            avg_calls = sum(tool_call_counts) / len(tool_call_counts)
            print(f"\n📊 每次对话平均调用 {avg_calls:.1f} 个工具")

        # 首 token 延迟
        first_tokens = [t["first_token_ms"] for t in traces if t.get("first_token_ms")]
        if first_tokens:
            avg_ft = sum(first_tokens) / len(first_tokens)
            print(f"📊 平均首 token 延迟: {avg_ft:.0f}ms ({avg_ft/1000:.1f}s)")

        # Token 消耗
        total_in = sum(t.get("tokens_input", 0) or 0 for t in traces)
        total_out = sum(t.get("tokens_output", 0) or 0 for t in traces)
        if total_in or total_out:
            print(f"📊 Token 消耗: 输入 {total_in} / 输出 {total_out}")
            # DeepSeek 当前价格约 ¥1/百万 token
            cost = (total_in + total_out) / 1_000_000 * 1
            print(f"📊 总成本约 ¥{cost:.4f} (按 ¥1/百万 token 估算)")

    print("\n✅ 测试完成")
