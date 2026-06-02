import json
import re
import uuid
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL
from retriever import ShoeRetriever
from tools import create_tools

# ===== 1. LLM 客户端 =====
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
# {user_context} 在运行时注入，未登录时为空字符串
SYSTEM_PROMPT_TEMPLATE = """你是 AI 鞋类导购助手。你必须主动使用工具搜索商品。

行为规则：
1. 用户提到鞋类需求 → 立即调 search_products 搜索
2. 用户描述穿搭 → 立即调 analyze_outfit
3. 用户要求对比 → 立即调 compare_shoes
4. 信息不够时 → 调 ask_clarify 追问，问完继续搜
5. 最终推荐时，必须在回复末尾输出 JSON，用 ```json 代码块包裹：

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
- 用自然的口语中文，像真人导购在跟你聊天
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


# ===== 3. 对话记忆（内存字典）=====
conversations: dict[str, list] = {}


def _get_history(conversation_id: str) -> list:
    """获取会话历史，新会话自动创建"""
    if not conversation_id:
        conversation_id = str(uuid.uuid4())[:8]
    if conversation_id not in conversations:
        conversations[conversation_id] = []
    return conversations[conversation_id], conversation_id


def _trim_history(history: list, max_rounds: int = 10):
    """截断历史，保留最近 max_rounds 轮（每轮 = HumanMessage + AIMessage）"""
    max_messages = max_rounds * 2
    while len(history) > max_messages:
        history.pop(0)
        history.pop(0)


# 工具名 → 中文状态文案（前端显示用）
TOOL_STATUS_MAP = {
    "search_products": "正在为你搜索合适的鞋款…",
    "analyze_outfit": "正在分析穿搭风格…",
    "compare_shoes": "正在对比两双鞋的优劣…",
    "ask_clarify": "想再确认一下你的需求…",
    "_default": "正在思考…",
}


# ===== 4. 核心：处理用户消息（非流式）=====
def process_message(conversation_id: str | None, user_message: str,
                    products: list[dict], user_context: str = "") -> dict:
    history, conversation_id = _get_history(conversation_id)
    retriever = ShoeRetriever(products)
    tools = create_tools(products, retriever)
    system_prompt = _build_system_prompt(user_context)
    agent = create_agent(llm, tools, system_prompt=system_prompt)

    messages = history + [HumanMessage(content=user_message)]
    result = agent.invoke({"messages": messages})

    output = result["messages"][-1].content

    history.append(HumanMessage(content=user_message))
    history.append(AIMessage(content=output))
    _trim_history(history)

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
                       products: list[dict], user_context: str = ""):
    """异步生成器，逐 token yield SSE 事件。
    额外 yield on_tool_start 事件让前端展示"正在搜索…"状态。"""
    history, conversation_id = _get_history(conversation_id)
    retriever = ShoeRetriever(products)
    tools = create_tools(products, retriever)
    system_prompt = _build_system_prompt(user_context)
    agent = create_agent(streaming_llm, tools, system_prompt=system_prompt)

    input_messages = history + [HumanMessage(content=user_message)]
    full_text = ""

    try:
        async for event in agent.astream_events(
            {"messages": input_messages},
            version="v2"
        ):
            kind = event.get("event", "")

            # 工具开始执行 → 通知前端显示状态
            if kind == "on_tool_start":
                tool_name = event.get("name", "")
                status = TOOL_STATUS_MAP.get(tool_name, TOOL_STATUS_MAP["_default"])
                yield f"data: {json.dumps({'status': status})}\n\n"

            # LLM 产出 token → 逐字推送
            elif kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    full_text += chunk.content
                    yield f"data: {json.dumps({'token': chunk.content})}\n\n"

            # 工具执行结束 → 通知前端可以恢复打字状态
            elif kind == "on_tool_end":
                yield f"data: {json.dumps({'status': ''})}\n\n"

    except Exception:
        # astream_events 失败时，降级为非流式一次性返回
        result = agent.invoke({"messages": input_messages})
        full_text = result["messages"][-1].content
        yield f"data: {json.dumps({'token': full_text})}\n\n"

    # 保存到历史
    history.append(HumanMessage(content=user_message))
    history.append(AIMessage(content=full_text))
    _trim_history(history)

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
