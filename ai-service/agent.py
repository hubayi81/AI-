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

# ===== 2. 系统提示词 =====
SYSTEM_PROMPT = """你是 AI 鞋类导购助手。你必须主动使用工具搜索商品。

行为规则：
1. 用户提到鞋类需求 → 立即调 search_products 搜索
2. 用户描述穿搭 → 立即调 analyze_outfit
3. 用户要求对比 → 立即调 compare_shoes
4. 信息不够时 → 调 ask_clarify 追问，问完继续搜
5. 最终推荐时，必须在回复末尾输出 JSON，用 ```json 代码块包裹：

```json
{"recommendations": [{"productId": 1, "name": "鞋名", "score": 95, "reason": "理由"}]}
score 是 0-100 的匹配度分数，最多推荐 5 款，按分数从高到低排序。
即使只有部分匹配的商品也要推荐，不要因为结果少就不推。"""


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


# ===== 4. 核心：处理用户消息 =====
def process_message(conversation_id: str | None, user_message: str,
                    products: list[dict]) -> dict:
    # 4a. 获取历史
    history, conversation_id = _get_history(conversation_id)

    # 4b. 构建语义检索器 + 工具
    retriever = ShoeRetriever(products)
    tools = create_tools(products, retriever)

    # 4c. 创建 Agent
    agent = create_agent(llm, tools, system_prompt=SYSTEM_PROMPT)

    # 4d. 拼接消息：历史 + 当前用户消息
    messages = history + [HumanMessage(content=user_message)]

    # 4e. 执行 Agent（ReAct 循环自动完成）
    result = agent.invoke({"messages": messages})

    # 4f. 取最后一条消息（LLM 最终回复）
    output = result["messages"][-1].content

    # 4g. 保存到历史
    history.append(HumanMessage(content=user_message))
    history.append(AIMessage(content=output))
    _trim_history(history)

    # 4h. 解析回复
    reply, action, results = _parse_reply(output)

    return {
        "conversation_id": conversation_id,
        "reply": reply,
        "action": action,
        "results": results,
    }


# ===== 5. 回复解析 =====
def _parse_reply(raw_reply: str) -> tuple[str, str, list | None]:
    """从 LLM 回复中提取推荐 JSON"""
    action = "chat"
    results = None

    try:
        # 策略1: ```json 代码块
        if "```json" in raw_reply:
            json_str = raw_reply.rsplit("```json", 1)[1].split("```", 1)[0].strip()
        # 策略2: 整段就是 JSON
        elif raw_reply.strip().startswith("{") and "recommendations" in raw_reply:
            json_str = raw_reply.strip()
        # 策略3: 从 { 到 } 截取
        elif "productId" in raw_reply:
            start = raw_reply.index("{")
            end = raw_reply.rindex("}") + 1
            json_str = raw_reply[start:end]
        else:
            return raw_reply, "chat", None

        parsed = json.loads(json_str)
        if "recommendations" in parsed and len(parsed["recommendations"]) > 0:
            results = parsed["recommendations"]
            if "compare" in json_str.lower() or "对比" in raw_reply:
                action = "compare"
            elif "outfit" in json_str.lower() or "穿搭" in raw_reply:
                action = "outfit"
            else:
                action = "recommend"
    except (json.JSONDecodeError, ValueError, KeyError):
        pass

    return raw_reply, action, results


