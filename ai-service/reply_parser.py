"""LLM 回复解析 —— 纯函数，无 IO、无模块级副作用，便于单测。

从 Agent 的流式/完整文本里抽两类结构化信息：
  - 商品推荐 JSON（recommendations 数组）
  - 追问建议（followUps 数组，截断到 3 个）

解析失败（JSON 损坏、没有结构）时，降级为「整段原文 + action=chat」，
不抛异常——这是 Agent 对外输出的一道容错，避免一条坏 JSON 让整次对话 500。
"""

import json


def parse_reply(raw_reply: str) -> tuple[str, str, list | None, list | None]:
    """从 LLM 回复中提取推荐 JSON + 追问建议。

    Returns:
        (原文, action, recommendations|None, followUps|None)
        action ∈ {recommend, compare, outfit, chat}
    """
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
