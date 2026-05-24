# LangChain Agent 搭建指南 — AI 鞋类导购助手

> 本文档是教学文档，也是开发文档。每一节都是你先理解再动手的基础。

---

## 一、LangChain 是什么？为什么要用它？

### 1.1 一句话

**LangChain 是 LLM 应用开发框架**，帮你把"调 API → 处理返回 → 调工具 → 再调 API"这个循环标准化。

### 1.2 不用框架 vs 用框架

| | 手搓 | LangChain |
|---|---|---|
| 调 DeepSeek API | 自己写 `requests.post` | `ChatOpenAI(model="deepseek-chat")` |
| 工具定义 | 手动拼 JSON Schema 字符串 | `@tool` 装饰器自动生成 |
| Function Calling 循环 | 手写 while 循环判断 | `create_react_agent` 自动完成 |
| 对话记忆 | 手动拼接消息列表 | `HumanMessage` / `AIMessage` 结构化管理 |

### 1.3 核心概念

```
LangChain 三大核心：

1. Model（模型）      → ChatOpenAI 封装了 DeepSeek API
2. Tool（工具）        → @tool 装饰器把 Python 函数变成 LLM 可调用的工具
3. Agent（智能体）     → create_react_agent 把 Model + Tool 组合成自主决策循环
```

---

## 二、Agent 是什么？ReAct 模式解释

### 2.1 ReAct = Reasoning + Acting

Agent 的核心思想叫 **ReAct**（推理 + 行动）：

```
Thought（思考）→ Action（行动）→ Observation（观察）→ Thought（再思考）→ ...
```

### 2.2 具体流程（以本项目为例）

```
用户："我脚宽跑步预算500"
  │
  ▼
┌─ Thought ─────────────────────────────────────┐
│ 用户想要跑鞋，预算 ≤500，关注宽楦。           │
│ 我应该调用 search_products 搜索商品。          │
└──────────────┬───────────────────────────────┘
               │ Action: search_products(keyword="宽楦", category="跑鞋", max_price=500)
               ▼
┌─ Observation ─────────────────────────────────┐
│ 返回 8 款匹配商品（Air Zoom Pegasus,          │
│ Ultraboost, Gel-Kayano...）                   │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌─ Thought ─────────────────────────────────────┐
│ 有 8 款，太多。需要缩小范围。                 │
│ 应该追问用户偏好的缓震类型。                  │
└──────────────┬───────────────────────────────┘
               │ Action: ask_clarify("需要缓震型还是稳定支撑型？")
               ▼
┌─ Observation ─────────────────────────────────┐
│ 用户回答："缓震的"                            │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌─ Final Answer ────────────────────────────────┐
│ "根据你的需求，推荐以下 3 款缓震跑鞋：        │
│  1. Gel-Kayano — 95分，顶级缓震，宽楦友好... │
│  2. Ultraboost — 90分，全掌boost，脚感柔软..."│
└──────────────────────────────────────────────┘
```

### 2.3 create_react_agent 做了什么

```python
agent = create_react_agent(model, tools, prompt=system_prompt)
```

这一行代码背后，LangGraph 自动完成了：

1. 把 `prompt`（系统提示）+ 用户消息 发给 LLM
2. LLM 返回 → 判断是"调用工具"还是"直接回复"
3. 如果是工具调用 → 执行对应 Python 函数 → 把结果送回 LLM → 回到第 2 步
4. 如果是直接回复 → 结束循环，返回最终结果

**你不用写 while 循环、不用手动判断、不用手动拼接消息——这些都自动完成了。**

---

## 三、项目架构

### 3.1 整体架构

```
用户浏览器 (index.html)
    │  POST /api/ai/chat
    ▼
Java Spring Boot (端口 8080)
    │  1. 从数据库查全部商品
    │  2. 调 Python Agent 服务
    │  3. 返回结果给前端
    ▼
Python Flask Agent 服务 (端口 5000)
    │  POST /api/ai/agent/chat
    │
    ├── app.py    → Flask 路由，接收请求
    ├── agent.py  → Agent 核心，调 create_react_agent
    ├── tools.py  → 4 个工具的定义与执行
    └── config.py → 读 .env 中的 API Key
    ▼
DeepSeek API (api.deepseek.com)
```

### 3.2 文件职责（Python 侧）

```
ai-service/
├── .env              # API Key（不提交到 Git）
├── .gitignore        # 忽略 .env、__pycache__ 等
├── requirements.txt  # 依赖清单
├── config.py         # 读环境变量（~10 行）
├── tools.py          # 4 个工具的定义 + 商品筛选逻辑（~90 行）
├── agent.py          # Agent 核心 + 对话记忆管理（~90 行）
└── app.py            # Flask 入口 + 路由（~40 行）
```

### 3.3 依赖方向（单向，禁止循环）

```
app.py  →  agent.py  →  tools.py
  │            │
  └────────────┴──→  config.py
```

---

## 四、四个工具（Tools）设计

### 4.1 工具是什么

在 LangChain 中，工具 = 一个 Python 函数 + 一段描述文字。LLM 通过描述文字理解"什么时候该调用这个工具"。

```python
@tool
def search_products(keyword: str = "", category: str = "", ...) -> str:
    """在商品库中搜索鞋款。参数：keyword: 功能关键词..."""
    # 筛选逻辑
    return json.dumps(匹配的商品列表)
```

`@tool` 装饰器会自动：
- 读取函数签名 → 生成 JSON Schema（给 LLM 看的参数格式）
- 读取 docstring → 生成工具描述（给 LLM 看的用途说明）

### 4.2 四个工具清单

| 工具 | 触发场景 | 输入 | 输出 |
|------|----------|------|------|
| `search_products` | 用户描述鞋类需求 | keyword, category, brand, gender, min_price, max_price | JSON 商品列表 |
| `analyze_outfit` | 用户描述穿搭 | top_wear, bottom_wear, occasion, style | JSON 商品列表 |
| `compare_shoes` | 用户要对比两双鞋 | product_id_1, product_id_2 | 两双鞋的详细信息 |
| `ask_clarify` | 信息不够需要追问 | question | 追问文本 |

### 4.3 商品数据从哪里来

Agent 不直连数据库。每次请求时，**Java 后端查好全部商品**，通过 HTTP 请求传给 Python：

```json
// Java → Python 的请求体
{
  "conversation_id": "abc123",
  "message": "脚宽跑步预算500",
  "products": [
    {"id": 1, "name": "Air Zoom Pegasus", "brand": "Nike", "price": 399, ...},
    {"id": 2, "name": "Ultraboost", "brand": "Adidas", "price": 450, ...}
  ]
}
```

> **为什么这样设计？** 因为 Agent 是无状态服务，不持有数据库连接，商品数据由调用方（Java）传入。这样 Python 服务可以独立部署、独立扩容。

---

## 五、对话记忆（Memory）设计

### 5.1 为什么需要记忆

LLM 每次调用是**无状态**的——它不知道上一轮你说了什么。所以我们需要在服务端保存历史消息，每次请求时把历史消息一起发给 LLM。

### 5.2 实现方式

```python
# 内存字典，key=会话ID，value=该会话的历史消息列表
conversations = {
    "abc123": [
        HumanMessage("脚宽跑步预算500"),
        AIMessage("我帮你搜到8款跑鞋，需要缓震的还是稳定的？"),
        HumanMessage("缓震的"),
        AIMessage("推荐以下3款..."),
    ],
    "def456": [...]
}
```

### 5.3 记忆窗口

- 每个会话保留**最近 10 轮**对话（= 20 条消息：10条用户 + 10条AI）
- 超过 10 轮时，删除最早的一对消息
- 服务重启后所有记忆丢失（内存存储，不做持久化）

---

## 六、接口规范

### 6.1 POST /api/ai/agent/chat

**请求**：

```json
{
  "conversation_id": "abc123",
  "message": "我平时跑5公里脚有点宽预算500以内",
  "products": [ ... ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| conversation_id | string | 否 | 首次传 null，后续传上次返回的 id |
| message | string | 是 | 用户说的自然语言 |
| products | array | 是 | Java 查好的全部商品列表 |

**返回**：

```json
{
  "conversation_id": "abc123",
  "reply": "根据你跑5公里需要缓震、脚偏宽的特点，推荐以下3款：...",
  "action": "recommend",
  "results": [
    {
      "productId": 3,
      "name": "Gel-Kayano 30",
      "score": 95,
      "reason": "顶级缓震跑鞋，鞋楦偏宽，适合脚宽跑者"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| conversation_id | string | 会话ID，前端存好，下次请求带上 |
| reply | string | AI 的文字回复 |
| action | string | `chat` / `recommend` / `outfit` / `compare` |
| results | array | 推荐结果，action=chat 时为 null |

### 6.2 GET /health

```json
{ "status": "ok" }
```

Java 后端通过这个接口判断 AI 服务是否在线。

---

## 七、Agent 核心代码预览

### 7.1 agent.py 核心流程

```python
from langgraph.prebuilt import create_react_agent

# 1. 创建 LLM 客户端
llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
)

# 2. 创建 Agent（模型 + 工具 + 系统提示）
agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)

# 3. 处理用户消息
def process_message(conversation_id, user_message, products):
    # 3a. 注入商品数据给工具使用
    set_products(products)

    # 3b. 拼接历史消息 + 当前消息
    messages = history + [HumanMessage(content=user_message)]

    # 3c. 执行 Agent（自动完成 ReAct 循环）
    result = agent.invoke({"messages": messages})

    # 3d. 提取 LLM 最终回复
    output = result["messages"][-1].content

    # 3e. 保存到历史
    history.append(HumanMessage(content=user_message))
    history.append(AIMessage(content=output))

    # 3f. 解析回复中的推荐 JSON
    reply, action, results = parse_reply(output)

    return { ... }
```

### 7.2 关键点解释

**Q: 为什么用 `agent.invoke({"messages": messages})`？**

这个 `invoke` 会：
1. 把 messages 发给 DeepSeek
2. 如果 DeepSeek 返回工具调用 → 自动执行工具 → 把结果送回 DeepSeek
3. 重复直到 DeepSeek 返回纯文本回复
4. 返回完整的消息列表（包含所有中间步骤）

**Q: `result["messages"][-1]` 是什么？**

`result["messages"]` 是一个列表，包含整个 ReAct 循环中所有消息：
```
[
  SystemMessage("你是导购助手..."),
  HumanMessage("脚宽跑步预算500"),
  AIMessage(tool_calls=[search_products(...)]),    ← LLM 决定调工具
  ToolMessage("返回了8款鞋..."),                    ← 工具执行结果
  AIMessage("推荐以下3款：..."),                    ← LLM 最终回复 ← 这就是 [-1]
]
```

最后一条 `AIMessage` 就是 LLM 给用户的最终回复。

---

## 八、开发步骤

| 步骤 | 内容 | 涉及文件 | 验证方式 |
|------|------|----------|----------|
| 1 | 确认依赖安装 | `requirements.txt` | `pip install -r requirements.txt` 无报错 |
| 2 | 确认环境变量 | `.env` | Python 能读到 key |
| 3 | 重写 `agent.py` | `agent.py` | 单独运行，发消息能收到 AI 回复 |
| 4 | 端到端测试 | `app.py` + `test.py` | `curl` 发消息，Agent 返回推荐结果 |
| 5 | Java 侧对接 | （后续步骤） | Postman 测试 `/api/ai/chat` |
| 6 | 前端对话界面 | （后续步骤） | 浏览器里完成一次对话推荐 |

---

## 九、安装的依赖

```
flask==3.1.0             # Web 框架，提供 HTTP 接口
python-dotenv==1.1.0     # 读 .env 文件
langchain>=0.3.0         # LangChain 核心（自动安装 langgraph, langchain-core, langchain-openai）
langchain-openai>=0.2.0  # ChatOpenAI，兼容 DeepSeek API
```

当前实际安装版本：`langchain 1.3.0` + `langgraph 1.2.0`

---

## 十、和旧版代码的关键区别

| | 旧代码（agent.py 当前） | 新代码（LangGraph） |
|---|---|---|
| Agent 创建 | `create_tool_calling_agent` + `AgentExecutor` | `create_react_agent` |
| 记忆管理 | `ConversationBufferWindowMemory` | 手动 `list[HumanMessage, AIMessage]` |
| API 稳定性 | 在 LangChain 1.3 中**已废弃** | 当前推荐方式 |
| 代码量 | 类似 | 类似 |
| 学习价值 | 学的是过时 API | 学的是当前主流方式 |

---

> **下一步**：确认本文档没问题后，开始第 3 步——重写 `agent.py`。
