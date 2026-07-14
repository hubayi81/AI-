"""
Agent 量化评测引擎。

4 个核心指标：
1. 任务成功率 — Agent 是否完成了用户需求（回复含关键术语/返回足够商品）
2. 平均推理步数 — Agent 执行了多少步（从 trace 的 tool_calls 拿）
3. 工具调用准确率 — Agent 是否调了正确的工具
4. 影子测试对比 — 同一 query，Agent vs 裸 LLM（无工具），对比回复质量

用法：
    python eval_engine.py             # 跑全部 30 条
    python eval_engine.py --fast      # 只跑快测 10 条
"""

import io
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta

# Windows 终端 GBK 乱码修复
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ.pop("SSLKEYLOGFILE", None)

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL
from eval_dataset import EVAL_CASES

# 北京时区
TZ = timezone(timedelta(hours=8))

# ─── 评测用商品数据（和 test.py 保持一致，覆盖多品牌多品类）───
PRODUCTS = [
    {"id": 1, "name": "Air Zoom Pegasus 41", "brand": "Nike", "category": "跑鞋", "gender": "male", "price": 899, "description": "轻量缓震跑鞋，Zoom Air 气垫，适合日常训练和 5-10 公里路跑", "imageUrl": ""},
    {"id": 2, "name": "Ultraboost 5X", "brand": "Adidas", "category": "跑鞋", "gender": "unisex", "price": 1099, "description": "Boost 中底全掌缓震，Primeknit 飞织鞋面，脚感软弹适合日常通勤和恢复跑", "imageUrl": ""},
    {"id": 3, "name": "Gel-Kayano 30", "brand": "Asics", "category": "跑鞋", "gender": "male", "price": 1190, "description": "支撑稳定型跑鞋，DUOMAX 双密度中底，适合扁平足和过度内旋跑者", "imageUrl": ""},
    {"id": 4, "name": "Old Skool", "brand": "Vans", "category": "板鞋", "gender": "unisex", "price": 569, "description": "经典侧边条纹板鞋，耐磨硫化底，街头滑板风格", "imageUrl": ""},
    {"id": 5, "name": "Chuck Taylor All Star", "brand": "Converse", "category": "帆布鞋", "gender": "unisex", "price": 499, "description": "经典高帮帆布鞋，百搭单品，适合日常休闲", "imageUrl": ""},
    {"id": 6, "name": "Air Jordan 1 Low", "brand": "Nike", "category": "篮球鞋", "gender": "male", "price": 999, "description": "飞人经典低帮款，Air Sole 气垫，复古篮球鞋风格", "imageUrl": ""},
    {"id": 7, "name": "Cloudmonster 2", "brand": "On", "category": "跑鞋", "gender": "unisex", "price": 1299, "description": "CloudTec 镂空中底，极致缓震回弹，适合长距离路跑", "imageUrl": ""},
    {"id": 8, "name": "Classic Clog", "brand": "Crocs", "category": "休闲鞋", "gender": "unisex", "price": 399, "description": "轻便洞洞鞋，Croslite 材质，透气不闷脚，夏天必备", "imageUrl": ""},
    {"id": 9, "name": "Dunk Low", "brand": "Nike", "category": "运动鞋", "gender": "female", "price": 749, "description": "复古 Dunk 系列，配色清新百搭，适合日常通勤和逛街", "imageUrl": ""},
    {"id": 10, "name": "Gazelle Bold", "brand": "Adidas", "category": "休闲鞋", "gender": "female", "price": 799, "description": "厚底增高休闲鞋，翻毛皮鞋面，时尚复古风格", "imageUrl": ""},
    {"id": 11, "name": "Fresh Foam X 1080v13", "brand": "New Balance", "category": "跑鞋", "gender": "unisex", "price": 999, "description": "Fresh Foam X 顶级缓震中底，宽楦版本可选 2E/4E，适合宽脚跑者", "imageUrl": ""},
    {"id": 12, "name": "Adizero SL", "brand": "Adidas", "category": "竞速跑鞋", "gender": "male", "price": 699, "description": "Lightstrike Pro 中底，轻量竞速训练鞋，适合速度训练和比赛", "imageUrl": ""},
    {"id": 13, "name": "Gel-Nimbus 26", "brand": "Asics", "category": "跑鞋", "gender": "female", "price": 1290, "description": "PureGEL 顶级缓震，FF BLAST+ 中底，适合高足弓和需要软底的人群", "imageUrl": ""},
    {"id": 14, "name": "Speedcat OG", "brand": "Puma", "category": "板鞋", "gender": "unisex", "price": 699, "description": "复古赛车鞋薄底设计，翻毛皮+皮革拼接，适合窄脚瘦脚人群", "imageUrl": ""},
    {"id": 15, "name": "Go Walk 7", "brand": "Skechers", "category": "健步鞋", "gender": "unisex", "price": 599, "description": "Hyper Burst 超轻中底，一脚蹬设计，适合日常走路和久站", "imageUrl": ""},
]

# 无工具 LLM（影子测试用）
shadow_llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    temperature=0.3,
)

SHADOW_PROMPT = """你是鞋类推荐助手。用户会用自然语言描述需求，你需要给出推荐。

你可以利用你的鞋类知识（材质、足型、品牌等）来回答，但你**不能搜索真实商品库**。
请直接回复，给出具体建议。

用户需求："""


def run_agent(query: str) -> dict:
    """跑一次 Agent，返回结果 + 追踪数据"""
    from agent import process_message

    conv_id = f"eval_{int(time.time() * 1000)}"
    t0 = time.time()
    result = process_message(
        conversation_id=conv_id,
        user_message=query,
        products=PRODUCTS,
        user_context="",
        history=None,
    )
    elapsed = time.time() - t0

    # 按 conversation_id 精准拿工具调用
    tool_calls = _get_trace_tools(conv_id)

    return {
        "reply": result.get("reply", ""),
        "action": result.get("action", ""),
        "results": result.get("results") or [],
        "tool_calls": tool_calls,
        "tool_count": len(tool_calls),
        "elapsed_ms": round(elapsed * 1000),
    }


def _get_trace_tools(conversation_id: str) -> list[dict]:
    """从 traces.db 按 conversation_id 拿工具调用记录"""
    try:
        db_path = os.path.join(os.path.dirname(__file__), "traces.db")
        db = sqlite3.connect(db_path)
        row = db.execute(
            "SELECT tool_calls FROM agent_traces WHERE conversation_id = ? ORDER BY timestamp DESC LIMIT 1",
            (conversation_id,),
        ).fetchone()
        db.close()
        if row and row[0]:
            return json.loads(row[0])
    except Exception:
        pass
    return []


def run_shadow(query: str) -> dict:
    """裸 LLM 影子测试——同样的问题，不给工具"""
    t0 = time.time()
    try:
        resp = shadow_llm.invoke([HumanMessage(content=SHADOW_PROMPT + query)])
        reply = resp.content
    except Exception as e:
        reply = f"[ERROR] {e}"
    elapsed = time.time() - t0
    return {"reply": reply, "elapsed_ms": round(elapsed * 1000)}


def evaluate_case(case: dict) -> dict:
    """评测单条用例"""
    qid = case["id"]
    query = case["query"]

    # Agent 跑
    agent_result = run_agent(query)
    agent_reply = agent_result["reply"]
    tool_names = [t.get("name", "") for t in agent_result["tool_calls"]]

    # ── 工具调用准确率 ──
    expected = set(case["expected_tools"])
    actual = set(tool_names)
    tool_hit = len(expected & actual) > 0  # 至少命中一个期望工具

    # ── 商品匹配 ──
    result_count = len(agent_result["results"])
    min_ok = result_count >= case["min_results"] if case["min_results"] > 0 else True

    # ── 关键词匹配 ──
    term_hits = 0
    for term in case["key_terms"]:
        if term.lower() in agent_reply.lower():
            term_hits += 1
    term_rate = term_hits / len(case["key_terms"]) if case["key_terms"] else 1.0

    # ── 综合成功判定 ──
    # 核心原则：Agent 只要给出了有用的回复就算成功
    #   - 返回了商品 → 搜索成功
    #   - 提到了关键知识 → 知识检索成功
    #   - 主动追问（结果为空但回复合理）→ 追问成功
    has_results = result_count > 0
    has_knowledge = term_rate >= 0.5 and len(case["key_terms"]) > 0
    has_clarify = "ask_clarify" in tool_names

    if case["intent"] == "knowledge":
        success = tool_hit or has_knowledge
    elif case["intent"] == "search":
        # 搜索意图：有结果 > 工具命中 > 关键词匹配
        success = has_results or tool_hit
    elif case["intent"] in ("compare", "outfit"):
        success = tool_hit or has_results or term_rate >= 0.3
    elif case["intent"] == "clarify":
        # 追问意图：调了 ask_clarify 或 Agent 主动追问了
        success = tool_hit or has_clarify or (result_count == 0 and "?" in agent_reply)
    else:
        success = tool_hit or has_results or term_rate >= 0.5

    # ── 影子测试 ──
    shadow = run_shadow(query)

    return {
        "id": qid,
        "query": query,
        "intent": case["intent"],
        "success": success,
        "tool_names": tool_names,
        "tool_hit": tool_hit,
        "tool_count": agent_result["tool_count"],
        "result_count": result_count,
        "term_rate": round(term_rate, 2),
        "agent_ms": agent_result["elapsed_ms"],
        "shadow_ms": shadow["elapsed_ms"],
        "agent_reply_preview": agent_reply[:200],
        "shadow_reply_preview": shadow["reply"][:200],
    }


def print_report(results: list[dict]):
    """打印评测报告"""
    total = len(results)
    successes = [r for r in results if r["success"]]
    success_rate = len(successes) / total * 100

    # 按意图分组
    by_intent = {}
    for r in results:
        intent = r["intent"]
        if intent not in by_intent:
            by_intent[intent] = []
        by_intent[intent].append(r)

    print("=" * 70)
    print("  🏃 Agent 量化评测报告")
    print(f"  时间: {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  用例数: {total}")
    print("=" * 70)

    # ── 总览 ──
    avg_steps = sum(r["tool_count"] for r in results) / total
    total_tool_hits = sum(1 for r in results if r["tool_hit"])
    tool_accuracy = total_tool_hits / total * 100
    avg_agent_ms = sum(r["agent_ms"] for r in results) / total
    avg_shadow_ms = sum(r["shadow_ms"] for r in results) / total

    print(f"\n📊 总览指标")
    print(f"  任务成功率:     {success_rate:.1f}%  ({len(successes)}/{total})")
    print(f"  工具调用准确率: {tool_accuracy:.1f}%  ({total_tool_hits}/{total})")
    print(f"  平均推理步数:   {avg_steps:.1f} 步/次")
    print(f"  Agent 平均耗时: {avg_agent_ms:.0f} ms")
    print(f"  LLM 裸调耗时:   {avg_shadow_ms:.0f} ms  (影子测试)")

    # ── 按意图 ──
    print(f"\n📋 按意图分类")
    intent_labels = {
        "search": "商品搜索", "knowledge": "知识检索",
        "outfit": "穿搭分析", "compare": "商品对比", "clarify": "模糊需求追问",
    }
    for intent, cases in sorted(by_intent.items()):
        s = sum(1 for c in cases if c["success"])
        avg_s = sum(c["tool_count"] for c in cases) / len(cases)
        label = intent_labels.get(intent, intent)
        bar = "█" * int(s / len(cases) * 20) + "░" * (20 - int(s / len(cases) * 20))
        print(f"  {label:8s}  {bar}  {s}/{len(cases)} ({s/len(cases)*100:.0f}%)  平均 {avg_s:.1f} 步")

    # ── 影子测试对比 ──
    agent_reply_lens = [len(r["agent_reply_preview"]) for r in results]
    shadow_reply_lens = [len(r["shadow_reply_preview"]) for r in results]
    agent_has_product = sum(1 for r in results if r["result_count"] > 0)

    print(f"\n🆚 影子测试对比（Agent vs 裸 LLM 无工具）")
    print(f"  Agent 返回结构化商品: {agent_has_product}/{total} ({agent_has_product/total*100:.0f}%)")
    print(f"  裸 LLM 无此能力（只能给文字建议）")
    print(f"  Agent 平均耗时: {avg_agent_ms:.0f} ms  |  裸 LLM: {avg_shadow_ms:.0f} ms")
    print(f"  (Agent 慢 {avg_agent_ms - avg_shadow_ms:.0f}ms——多了工具调用，换来的是真实商品推荐)")

    # ── 失败用例 ──
    failures = [r for r in results if not r["success"]]
    if failures:
        print(f"\n❌ 失败用例 ({len(failures)}):")
        for f in failures:
            tools_str = ", ".join(f["tool_names"]) if f["tool_names"] else "(无工具调用)"
            print(f"  [{f['id']}] {f['query'][:40]}...")
            print(f"       调了: {tools_str}  结果数: {f['result_count']}  词命中率: {f['term_rate']}")
            print(f"       回复: {f['agent_reply_preview'][:120]}...")
            print()

    # ── 工具分布 ──
    tool_dist = {}
    for r in results:
        for name in r["tool_names"]:
            tool_dist[name] = tool_dist.get(name, 0) + 1
    if tool_dist:
        print(f"🔧 工具调用分布:")
        for name, cnt in sorted(tool_dist.items(), key=lambda x: -x[1]):
            bar = "█" * cnt
            print(f"  {name:20s} {bar} {cnt}")

    print()
    print("=" * 70)

    # ── 持久化 ──
    _save_report(results, success_rate, avg_steps, tool_accuracy)

    return success_rate, avg_steps, tool_accuracy


def _save_report(results: list[dict], success_rate: float,
                 avg_steps: float, tool_accuracy: float):
    """保存评测结果到 traces.db 的 eval_runs 表"""
    try:
        db_path = os.path.join(os.path.dirname(__file__), "traces.db")
        db = sqlite3.connect(db_path)
        db.execute("""
            CREATE TABLE IF NOT EXISTS eval_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_time TEXT,
                total_cases INTEGER,
                success_rate REAL,
                avg_steps REAL,
                tool_accuracy REAL,
                details TEXT
            )
        """)
        db.execute(
            "INSERT INTO eval_runs (run_time, total_cases, success_rate, avg_steps, tool_accuracy, details) VALUES (?,?,?,?,?,?)",
            (datetime.now(TZ).isoformat(), len(results), round(success_rate, 1),
             round(avg_steps, 2), round(tool_accuracy, 1), json.dumps(results, ensure_ascii=False)),
        )
        db.commit()
        db.close()
        print("  📁 结果已保存到 traces.db → eval_runs 表")
    except Exception as e:
        print(f"  ⚠️ 保存失败: {e}")


def main():
    fast = "--fast" in sys.argv
    cases = EVAL_CASES[:10] if fast else EVAL_CASES
    mode = "快测 10 条" if fast else f"全量 {len(cases)} 条"

    print(f"🚀 开始评测 ({mode})...\n")
    results = []

    for i, case in enumerate(cases):
        print(f"  [{i+1}/{len(cases)}] {case['id']} {case['query'][:50]}...", end=" ", flush=True)
        r = evaluate_case(case)
        results.append(r)
        status = "✅" if r["success"] else "❌"
        print(f"{status} 步数={r['tool_count']} 工具={'✓' if r['tool_hit'] else '✗'}")

    print()
    print_report(results)


if __name__ == "__main__":
    main()
