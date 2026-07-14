# AI 商品推荐 Agent — FastAPI 重写规范

> 版本 v3.0 | 2026-05-19

---

## 一、为什么重写

| 问题 | 现状 | 新方案 |
|------|------|--------|
| LangChain API 已废弃 | `create_tool_calling_agent` + `AgentExecutor` | `create_react_agent`（LangGraph） |
| 线程不安全 | `tools.py` 全局变量 `_products` | 闭包注入 `create_tools(products)` |
| 回复解析脆弱 | `parse_reply()` 手动抠 JSON | 多级回退解析 + 优化 prompt |

---

## 二、技术栈

| 组件 | 选型 |
|------|------|
| Web 框架 | FastAPI（异步、/docs、Pydantic） |
| LLM | DeepSeek `deepseek-chat` |
| Agent | `langgraph.prebuilt.create_react_agent` |
| 工具 | `@tool` 装饰器 |
| 记忆 | 内存 `dict[str, list]`，最近 10 轮 |
| 数据校验 | Pydantic v2 |

### 依赖

```
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
python-dotenv>=1.1.0
langchain>=0.3.0
langchain-openai>=0.3.0
langgraph>=0.4.0
```

---

## 三、项目结构

```
ai-service/
├── .env
├── requirements.txt
├── config.py           # 读 .env（不变）
├── schemas.py          # [新] Pydantic 模型
├── tools.py            # [重写] 工具工厂函数
├── agent.py            # [重写] Agent 核心 + 记忆
└── main.py             # [新] FastAPI 入口
```

依赖方向：`main.py → agent.py → tools.py`，全部依赖 `config.py`

---

## 四、API 接口

### POST /api/ai/agent/chat

请求：

```json
{
  "conversation_id": null,
  "message": "脚宽跑步预算500",
  "products": [
    {"id": 1, "name": "Air Zoom Pegasus", "brand": "Nike", "category": "跑鞋", "gender": "male", "price": 399, "description": "轻量缓震跑鞋", "color": "黑色", "sizeRange": "39-44", "stock": 10}
  ]
}
```

响应：

```json
{
  "conversation_id": "abc12345",
  "reply": "根据你的需求，推荐以下3款：",
  "action": "recommend",
  "results": [
    {"productId": 3, "name": "Gel-Kayano 30", "score": 95, "reason": "顶级缓震，宽楦友好"}
  ]
}
```

action 取值：`chat` | `recommend` | `outfit` | `compare`

### GET /health

```json
{ "status": "ok" }
```

---

## 五、Agent 流程

```
请求 → main.py 校验 → agent.process_message()
  → 获取/创建记忆
  → create_tools(products) 构建工具
  → create_react_agent(llm, tools, prompt)
  → agent.invoke() → DeepSeek ReAct 循环
  → 保存记忆 → 解析回复 → 返回
```

### 系统提示词

```
你是 AI 鞋类推荐助手。你可以使用工具搜索商品、分析穿搭、对比商品。

规则：
1. 鞋类需求 → search_products
2. 穿搭描述 → analyze_outfit
3. 对比需求 → compare_shoes
4. 信息不够 → ask_clarify 追问
5. 推荐时回复末尾附 JSON：
   {"recommendations": [{"productId": 1, "score": 95, "reason": "..."}]}
   最多 5 款，score 0-100
```

---

## 六、四个工具

| 工具 | 参数 | 返回 |
|------|------|------|
| `search_products` | keyword, category, brand, gender, min_price, max_price | JSON 数组，最多 8 条 |
| `analyze_outfit` | top_wear, bottom_wear, occasion, style | JSON 数组 |
| `compare_shoes` | product_id_1, product_id_2 | 两双鞋详细信息 |
| `ask_clarify` | question | `{"question": "..."}` |

关键改动：`create_tools(products)` 闭包注入数据，不用全局变量。

---

## 七、记忆设计

- 模块级 `dict[str, list[BaseMessage]]`
- 每个 conversation_id 保留最近 10 轮
- 超过截断最早的一对消息
- 纯内存，不持久化

---

## 八、Pydantic 模型

```python
class Product(BaseModel):
    id: int; name: str; brand: str; category: str; gender: str
    price: float; description: str = ""; color: str = ""; sizeRange: str = ""; stock: int = 0

class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str
    products: list[Product] = []

class RecommendResult(BaseModel):
    productId: int; name: str; score: int; reason: str

class ChatResponse(BaseModel):
    conversation_id: str; reply: str; action: str = "chat"; results: list[RecommendResult] | None = None
```

---

## 九、错误处理

| 场景 | 状态码 | 行为 |
|------|--------|------|
| 缺少必填字段 | 422 | Pydantic 自动返回 |
| DeepSeek API 失败 | 500 | 降级话术，不暴露原始错误 |
| LLM JSON 解析失败 | 200 | 返回纯文本，action=chat（降级） |

---

## 十、开发步骤

| 步骤 | 内容 | 验证 |
|------|------|------|
| 1 | 更新 `requirements.txt` | pip install 无报错 |
| 2 | 创建 `schemas.py` | Python 交互验证模型 |
| 3 | 重写 `tools.py` | 工具函数返回正确 |
| 4 | 重写 `agent.py` | 单条消息收到 Agent 回复 |
| 5 | 创建 `main.py` | uvicorn 启动，/docs 可测试 |
| 6 | 端到端测试 | 多轮对话验证记忆和推荐 |
| 7 | 清理旧文件 | 删除 app.py 等 |

---

## 十一、新旧对比

| | 旧版 v2.0 | 新版 v3.0 |
|---|---|---|
| 框架 | Flask 同步 | FastAPI 异步 |
| Agent API | `create_tool_calling_agent`（废弃） | `create_react_agent` |
| 数据注入 | 全局变量 | 闭包 |
| 校验 | 手写 | Pydantic 自动 |
| 接口文档 | 无 | `/docs` |
| 记忆 | `ConversationBufferWindowMemory` | 手动 `list[BaseMessage]` |
