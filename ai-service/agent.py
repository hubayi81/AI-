import hashlib
import json
import pickle
import re
import uuid

import redis
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, REDIS_HOST, REDIS_PORT, REDIS_DB
from retriever import ShoeRetriever, get_retriever
from tools import create_tools
from knowledge_base import KnowledgeBase
from trace import TraceContext

# 知识库：启动时加载一次，常驻内存，所有请求共享
# 为什么用全局变量？—— 知识库的 markdown 文件不会在运行时变化，
# 每次请求重新加载会浪费 I/O + 向量化计算
_knowledge_base = None

#【安全加载 + 降级机制】
def _get_knowledge_base() -> KnowledgeBase | None:
    """懒加载知识库，加载失败时返回 None（Agent 降级运行，不影响商品搜索）"""
    global _knowledge_base
    if _knowledge_base is None:
        try:
            _knowledge_base = KnowledgeBase()
        except Exception as e:
            print(f"[Agent] 知识库加载失败: {e}")
            _knowledge_base = False  # 标记为已尝试，避免反复重试
    return _knowledge_base if _knowledge_base is not False else None

# ===== 1. LLM 客户端 =====
# ① 创建 LLM 客户端（ChatOpenAI 封装 DeepSeek API）
llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    temperature=0.3,
)

# 流式 LLM（用于 SSE 端点）
streaming_llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    temperature=0.3,
    streaming=True,
)

# ===== 2. 系统提示词模板 =====
# ② 写 System Prompt（告诉 Agent 它是什么角色、什么时候该调哪个工具、输出格式要求）
# {user_context} 在运行时注入，未登录时为空字符串
SYSTEM_PROMPT_TEMPLATE = """你是 AI 鞋类推荐助手。你必须主动使用工具搜索商品。

行为规则：
1. 用户提到鞋类需求 → 立即调 search_products 搜索
2. 用户描述穿搭 → 立即调 analyze_outfit
3. 用户要求对比 → 立即调 compare_shoes
4. 信息不够时 → 调 ask_clarify 追问，问完继续搜
5. 用户问专业知识（材质对比/足型选鞋/运动场景/品牌特点/尺码/保养）→ 先调 search_knowledge 获取专业知识，再结合商品推荐。为什么先查知识？—— 有专业依据的推荐比"我觉得这双好"可信得多
6. 🔍 防幻觉双检规则（非常重要）：
   a) 禁止编造：只能使用 search_knowledge 返回的知识内容，不要自己编造鞋类专业知识
   b) 强制来源标注：引用知识时必须用"根据【XX领域·XX】"格式标注来源，例如"根据【材质科技·EVA 中底】"
   c) 置信度分级处理：高置信度（high）可直接引用；中置信度（medium）可引用但不要绝对语气；低置信度（low）标注"暂未完全确认"
   d) 知识未找到时：直接告知用户"我暂时没有这方面的资料"，不要试图猜测
7. 最终推荐时，必须在回复末尾输出 JSON，用 ```json 代码块包裹：

```json
{{
  "recommendations": [
    {{"productId": 1, "name": "鞋名", "score": 95, "reason": "理由"}}
  ],
  "followUps": ["追问1", "追问2"]
}}
```

followUps 是 2-3 个自然的后续追问，帮助用户进一步筛选，例如：
- "有更便宜的吗？"
- "适合宽脚吗？"
- "有女款类似的吗？"
- "可以再推荐一双透气性更好的吗？"
- "这鞋适合长时间走路吗？"

输出风格要求（非常重要）：
- 用自然的口语中文，像真人商品推荐在跟你聊天
- 禁止使用 markdown 标题（##、### 等）
- 禁止使用加粗（**文字**）
- 禁止使用 emoji 数字（1️⃣2️⃣3️⃣）和装饰符号（⭐✨🔥）
- 推荐列表用简单的 "1. 鞋名 - 价格" 格式
- 每款鞋的介绍控制在 2-3 句，简洁直接
- 不要写长篇大论，不要过度推销

score 是 0-100 的匹配度分数，最多推荐 5 款，按分数从高到低排序。
即使只有部分匹配的商品也要推荐，不要因为结果少就不推。

{user_context}"""


def _build_system_prompt(user_context: str = "") -> str:
    """构建最终系统提示词：模板 + 可选用户画像上下文"""
    if user_context:
        context_block = f"\n## 当前用户画像（供参考，不要逐字念出来）\n{user_context}\n"
    else:
        context_block = ""
    return SYSTEM_PROMPT_TEMPLATE.format(user_context=context_block)


# ===== 3. 对话记忆（Redis）=====
# Redis 客户端：惰性连接，首次调用时自动连接
# 为什么用 Redis 替代 Python dict？
# —— 1) 多 worker 共享：uvicorn 多 worker 时内存 dict 不互通，用户请求被负载到
#    不同 worker 会丢失对话上下文；Redis 是独立进程，所有 worker 共享
# —— 2) 持久化：Python 进程重启不丢对话（RDB/AOF 保障）
# —— 3) 原子操作：Redis String GET/SET 自带原子性，无需额外加锁
# —— 4) 自动过期：TTL 24 小时自动清理冷对话，不需要手动管理内存
# 降级策略：Redis 连接失败时回退到内存 dict，保证核心功能不挂（一线企业常用模式）
_redis_client: redis.Redis | None = None
_fallback_dict: dict[str, list] = {}  # Redis 挂掉时的降级存储
CONV_TTL = 3600 * 24  # 对话 24 小时后自动过期


def _get_redis() -> redis.Redis | None:
    """惰性连接 Redis，首次调用时连接。失败返回 None 触发降级。"""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
                socket_connect_timeout=2, socket_timeout=2,
                decode_responses=False,
            )
            _redis_client.ping()
            print(f"[Agent] Redis 连接成功: {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            print(f"[Agent] Redis 连接失败，降级到内存字典: {e}")
            _redis_client = False
    return _redis_client if _redis_client is not False else None


def _get_history(conversation_id: str) -> list:
    """获取会话历史。优先 Redis，连接失败时降级到内存字典。"""
    if not conversation_id:
        conversation_id = str(uuid.uuid4())[:8]

    r = _get_redis()
    if r:
        try:
            key = f"conv:{conversation_id}"
            data = r.get(key)
            if data:
                return pickle.loads(data), conversation_id
        except Exception:
            pass  # Redis 读失败，降级

    # 降级：使用内存字典
    if conversation_id not in _fallback_dict:
        _fallback_dict[conversation_id] = []
    return _fallback_dict[conversation_id], conversation_id


def _save_history(conversation_id: str, history: list):
    """持久化对话历史到 Redis。失败时静默降级到内存字典。"""
    r = _get_redis()
    if r:
        try:
            key = f"conv:{conversation_id}"
            r.setex(key, CONV_TTL, pickle.dumps(history))
            return
        except Exception:
            pass

    _fallback_dict[conversation_id] = history


def _trim_history(history: list, max_rounds: int = 10):
    """截断历史，保留最近 max_rounds 轮（每轮 = HumanMessage + AIMessage）"""
    max_messages = max_rounds * 2
    while len(history) > max_messages:
        history.pop(0)
        history.pop(0)


def _restore_history(target_list: list, history_data: list[dict]):
    """从持久化历史恢复对话记忆（Agent 启动后第一次对话时调用）。"""
    for msg in history_data[-20:]:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            target_list.append(HumanMessage(content=content))
        elif role in ("ai", "assistant"):
            target_list.append(AIMessage(content=content))


# 工具名 → 中文状态文案（前端显示用）
TOOL_STATUS_MAP = {
    "search_products": "正在为你搜索合适的鞋款…",
    "analyze_outfit": "正在分析穿搭风格…",
    "compare_shoes": "正在对比两双鞋的优劣…",
    "ask_clarify": "想再确认一下你的需求…",
    "search_knowledge": "正在查阅专业知识…",
    "_default": "正在思考…",
}

# 工具名 → 简短标签（前端气泡上的 tool tag 用）
TOOL_LABEL_MAP = {
    "search_products": "搜索鞋款",
    "analyze_outfit": "分析穿搭",
    "compare_shoes": "对比鞋款",
    "ask_clarify": "追问需求",
    "search_knowledge": "查阅知识",
    "_default": "思考中",
}


# ===== 4. 核心：处理用户消息（非流式）=====

def process_message(conversation_id: str | None, user_message: str,
                    products: list[dict], user_context: str = "",
                    history: list[dict] | None = None) -> dict:
    # —— 追踪：开始计时 ——
    trace_ctx = TraceContext(conversation_id=conversation_id or "")
    trace_ctx.start()
    error_msg = None

    history_list, conversation_id = _get_history(conversation_id)
    # Python 内存中没有这个对话的历史 → 从传入的持久化历史恢复
    # 场景：Python 服务刚重启，内存字典清空了，但 MySQL 里有记录
    if len(history_list) == 0 and history:
        _restore_history(history_list, history)
    retriever = get_retriever(products)
    tools = create_tools(products, retriever, _get_knowledge_base())
    system_prompt = _build_system_prompt(user_context)
    agent = create_agent(llm, tools, system_prompt=system_prompt)
    agent = agent.with_config({"recursion_limit": 15})

    messages = history_list + [HumanMessage(content=user_message)]

    try:
        result = agent.invoke({"messages": messages})
        output = result["messages"][-1].content
        # 从 LangChain 消息中提取工具调用（非流式不走 astream_events）
        for msg in result.get("messages", []):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    trace_ctx._tool_calls.append({
                        "name": tc.get("name", "unknown"),
                        "duration_ms": 0,  # 非流式拿不到中间耗时
                    })
    except Exception as e:
        output = "AI 暂时不可用，请稍后再试。"
        error_msg = str(e)

    # —— 追踪：结束计时，保存 ——
    # 非流式没有 first_token 时间，估算 token
    input_text = user_message + system_prompt
    tokens_in = TraceContext.estimate_tokens(input_text)
    tokens_out = TraceContext.estimate_tokens(output)
    trace_ctx.end(error=error_msg, tokens_input=tokens_in, tokens_output=tokens_out)

    history_list.append(HumanMessage(content=user_message))
    history_list.append(AIMessage(content=output))
    _trim_history(history_list)
    _save_history(conversation_id, history_list)

    reply, action, results, follow_ups = _parse_reply(output)

    return {
        "conversation_id": conversation_id,
        "reply": reply,
        "action": action,
        "results": results,
        "followUps": follow_ups,
    }


# ===== 5. 流式处理（SSE 用）=====
async def stream_agent(conversation_id: str | None, user_message: str,
                       products: list[dict], user_context: str = "",
                       history: list[dict] | None = None):
    """异步生成器，逐 token yield SSE 事件。
    额外 yield on_tool_start 事件让前端展示"正在搜索…"状态。"""
    # —— 追踪：开始计时 ——
    trace_ctx = TraceContext(conversation_id=conversation_id or "")
    trace_ctx.start()
    error_msg = None
    first_token_seen = False

    history_list, conversation_id = _get_history(conversation_id)
    # Python 内存中没有这个对话的历史 → 从传入的持久化历史恢复
    if len(history_list) == 0 and history:
        _restore_history(history_list, history)
    retriever = get_retriever(products)
    tools = create_tools(products, retriever, _get_knowledge_base())
    system_prompt = _build_system_prompt(user_context)
    agent = create_agent(streaming_llm, tools, system_prompt=system_prompt)
    agent = agent.with_config({"recursion_limit": 15})

    input_messages = history_list + [HumanMessage(content=user_message)]
    full_text = ""

    try:
        async for event in agent.astream_events(
            {"messages": input_messages},
            version="v2"
        ):
            kind = event.get("event", "")

            # 工具开始执行 → 通知前端 + 追踪计时
            if kind == "on_tool_start":
                tool_name = event.get("name", "")
                trace_ctx.on_tool_start(tool_name)
                status = TOOL_STATUS_MAP.get(tool_name, TOOL_STATUS_MAP["_default"])
                tool_label = TOOL_LABEL_MAP.get(tool_name, TOOL_LABEL_MAP["_default"])
                yield f"data: {json.dumps({'tool_start': tool_name, 'tool_label': tool_label, 'status': status})}\n\n"

            # LLM 产出 token → 逐字推送 + 标记首 token
            elif kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    if not first_token_seen:
                        first_token_seen = True
                        trace_ctx.on_first_token()
                    full_text += chunk.content
                    yield f"data: {json.dumps({'token': chunk.content})}\n\n"

            # 工具执行结束 → 通知前端 + 追踪记录耗时
            elif kind == "on_tool_end":
                trace_ctx.on_tool_end()
                tool_name = event.get("name", "")
                tool_label = TOOL_LABEL_MAP.get(tool_name, TOOL_LABEL_MAP["_default"])
                yield f"data: {json.dumps({'tool_end': tool_name, 'tool_label': tool_label, 'status': ''})}\n\n"

    except Exception as e:
        error_msg = str(e)
        # astream_events 失败时，降级为非流式一次性返回
        result = agent.invoke({"messages": input_messages})
        full_text = result["messages"][-1].content
        yield f"data: {json.dumps({'token': full_text})}\n\n"

    # —— 追踪：结束计时，估算 token + 保存 ——
    input_text = user_message + system_prompt
    tokens_in = TraceContext.estimate_tokens(input_text)
    tokens_out = TraceContext.estimate_tokens(full_text)
    trace_ctx.end(error=error_msg, tokens_input=tokens_in, tokens_output=tokens_out)

    # 保存到历史
    history_list.append(HumanMessage(content=user_message))
    history_list.append(AIMessage(content=full_text))
    _trim_history(history_list)
    _save_history(conversation_id, history_list)

    # 解析并发送最终结果（含 followUps）
    reply, action, results, follow_ups = _parse_reply(full_text)
    yield f"data: {json.dumps({'done': True, 'conversation_id': conversation_id, 'reply': full_text, 'action': action, 'results': results, 'followUps': follow_ups})}\n\n"


# ===== 6. 回复解析 =====
def _parse_reply(raw_reply: str) -> tuple[str, str, list | None, list | None]:
    """从 LLM 回复中提取推荐 JSON + 追问建议"""
    action = "chat"
    results = None
    follow_ups = None

    try:
        if "```json" in raw_reply:
            json_str = raw_reply.rsplit("```json", 1)[1].split("```", 1)[0].strip()
        elif raw_reply.strip().startswith("{") and "recommendations" in raw_reply:
            json_str = raw_reply.strip()
        elif "productId" in raw_reply:
            start = raw_reply.index("{")
            end = raw_reply.rindex("}") + 1
            json_str = raw_reply[start:end]
        else:
            return raw_reply, "chat", None, None

        parsed = json.loads(json_str)
        if "recommendations" in parsed and len(parsed["recommendations"]) > 0:
            results = parsed["recommendations"]
            if "compare" in json_str.lower() or "对比" in raw_reply:
                action = "compare"
            elif "outfit" in json_str.lower() or "穿搭" in raw_reply:
                action = "outfit"
            else:
                action = "recommend"
        # 提取追问建议
        if "followUps" in parsed and isinstance(parsed["followUps"], list):
            follow_ups = parsed["followUps"][:3]  # 最多 3 个
    except (json.JSONDecodeError, ValueError, KeyError):
        pass

    return raw_reply, action, results, follow_ups
