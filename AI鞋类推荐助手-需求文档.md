# AI 鞋类推荐助手 — Agent 开发需求文档

> 版本 v2.0 | 2026-05-14

---

## 一、项目概述

### 1.1 一句话描述

一个 **AI Agent 对话导购系统**：用户用自然语言和 AI 聊天，AI 自主决策调用工具（搜索商品、分析穿搭、追问偏好、对比商品），最终从真实数据库中找到匹配的鞋款并给出个性化推荐理由。

### 1.2 和普通 AI 问答的区别

| | 普通 AI | 本项目 |
|---|---|---|
| 数据 | 通用知识，可能推荐不存在的鞋 | 真实数据库，推的都是有库存的 |
| 交互 | 一问一答 | 多轮对话，AI 主动追问 |
| 决策 | 用户告诉系统做什么 | AI 自己决定调什么工具 |
| 结果 | 纯文本 | 结构化商品卡片 + 评分 + 理由 |

### 1.3 架构图

```
用户浏览器 (index.html)
    │  ← 对话消息 →
    ▼
Java Spring Boot (端口 8080)
    │  POST /api/ai/chat       ← Agent 对话入口
    │  GET  /api/products       ← 获取全部商品（Agent 需要时调用）
    │  GET  /api/products/{id}  ← 获取单个商品详情
    ▼
Python Flask Agent 服务 (端口 5000)
    │  POST /api/ai/agent/chat    ← Agent 核心
    │  GET  /health               ← 健康检查
    │
    │  Agent 决策引擎（Function Calling）
    │  ├── search_products   → 搜商品
    │  ├── analyze_outfit    → 穿搭分析
    │  ├── compare_shoes     → 商品对比
    │  └── ask_clarify       → 追问用户
    ▼
DeepSeek API
```

---

## 二、Agent 设计

### 2.1 Agent 是什么

Agent = LLM + 工具调用 + 记忆 + 决策循环

```
用户消息 → Agent（DeepSeek）→ 决定调用哪个工具？
           ↓ 工具返回结果    ↓ 不需要工具
           Agent 再思考      → 直接回复用户
           ↓ 还要调工具？
           循环直到 Agent 说"够了"
```

### 2.2 四个工具（Tools）

| 工具名 | 功能描述 | 输入参数 |
|--------|----------|----------|
| `search_products` | 在真实商品库中按条件匹配 | category, brand, gender, max_price, min_price, keyword |
| `analyze_outfit` | 根据用户穿搭描述推荐搭配的鞋 | top_wear, bottom_wear, occasion, style |
| `compare_shoes` | 对比两双鞋的优劣 | product_id_1, product_id_2 |
| `ask_clarify` | 向用户追问缺失信息 | question, options (可选候选项) |

### 2.3 Agent 决策流程

```
收到用户消息 "我平时跑步脚宽预算500"
    │
    ▼
Agent 分析：需要搜跑鞋、预算≤500、关注宽楦 → 调 search_products
    │
    ▼
search_products 返回 8 款匹配商品
    │
    ▼
Agent：有8款，再追问缩小范围 → 调 ask_clarify("需要缓震还是稳定支撑？")
    │
    ▼
用户："缓震的"
    │
    ▼
Agent：从8款中筛出缓震型 3 款 → 组织推荐语 → 返回用户
    │
    ▼
返回: { action: "recommend", results: [...3款带理由...] }
```

### 2.4 对话记忆

- 每个会话有唯一 `conversation_id`
- Agent 服务端内存维护最近 10 轮对话历史
- 超过 10 轮自动截断最早的，防止 prompt 过长
- 服务重启会丢失历史（内存存储，不做持久化）

---

## 三、接口规范

### 3.1 Python Agent 服务

- 地址：`http://localhost:5000`
- 数据格式：JSON
- 字符编码：UTF-8
- 启动方式：`python app.py`

#### POST /api/ai/agent/chat

**请求**：

```json
{
  "conversation_id": "abc123",
  "message": "我平时跑5公里脚有点宽预算500以内",
  "products": [
    {
      "id": 1,
      "name": "Air Zoom Pegasus",
      "brand": "Nike",
      "category": "跑鞋",
      "gender": "male",
      "price": 499,
      "description": "经典缓震跑鞋，适合日常训练",
      "color": "黑色",
      "sizeRange": "39-44",
      "stock": 15
    }
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| conversation_id | string | 否 | 首次传 null，后续传上次返回的 id |
| message | string | 是 | 用户说的自然语言 |
| products | array | 是 | 全部商品列表（Java 从 DB 查好后传入） |

**返回**：

```json
{
  "conversation_id": "abc123",
  "reply": "根据你跑5公里需要缓震、脚偏宽的特点，推荐以下3款：",
  "action": "recommend",
  "results": [
    {
      "productId": 3,
      "name": "Gel-Kayano 30",
      "score": 95,
      "reason": "顶级缓震跑鞋，鞋楦偏宽，适合脚宽跑者，价格¥499在你预算内"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| conversation_id | string | 会话ID，下次请求带上 |
| reply | string | AI 的对话回复（始终有值） |
| action | string | `chat`（纯聊天）/ `recommend`（推荐结果）/ `outfit`（穿搭结果）/ `compare`（对比结果） |
| results | array | 仅 recommend/outfit/compare 时有值，chat 时为 null |

#### GET /health

**返回**：

```json
{ "status": "ok" }
```

### 3.2 Java 后端新增接口

#### POST /api/ai/chat

**请求**：

```json
{
  "conversation_id": "abc123",
  "message": "我平时跑5公里脚有点宽预算500以内"
}
```

**返回**：透传 Python Agent 的返回，格式一致。

#### GET /api/ai/health

**返回**：

```json
{ "online": true }
```

---

## 四、前端交互设计

### 4.1 页面结构

```
┌────────────────────────────────────────────┐
│  🟢 AI鞋类导购 Agent                        │
├────────────────────────────────────────────┤
│                                            │
│  ┌── AI ─────────────────────────────────┐ │
│  │ 你好！想找什么鞋？可以直接告诉我        │ │
│  │ 你的需求，比如"跑步穿的缓震鞋"           │ │
│  │ 或者描述今天的穿搭我来帮你搭配           │ │
│  └───────────────────────────────────────┘ │
│                                            │
│  [🏃跑步] [🚶通勤] [👔穿搭] [🔍搜索]        │
│                                            │
│  ┌── 用户 ──┐                              │
│  │ 脚宽跑步预算500                          │
│  └──────────┘                              │
│                                            │
│  ┌── AI ─────────────────────────────────┐ │
│  │ 根据你的需求推荐以下3款：               │ │
│  │                                        │ │
│  │ ┌──────┐ ┌──────┐ ┌──────┐            │ │
│  │ │ 鞋1  │ │ 鞋2  │ │ 鞋3  │            │ │
│  │ │95分  │ │90分  │ │85分  │            │ │
│  │ │¥499  │ │¥450  │ │¥520  │            │ │
│  │ └──────┘ └──────┘ └──────┘            │ │
│  └───────────────────────────────────────┘ │
│                                            │
│  ┌────────────────────────────────────┐    │
│  │ 输入你想问的...              [发送] │    │
│  └────────────────────────────────────┘    │
└────────────────────────────────────────────┘
```

### 4.2 关键交互

- **快捷入口**：四个按钮一键填充常见场景
- **Loading 态**：AI 思考时显示打字动画
- **商品卡片**：嵌入对话流中，点击可展开详情
- **错误降级**：AI 服务挂了显示「AI 暂时不可用，请使用传统筛选」

---

## 五、Python 模块拆分

```
ai-service/
├── .env                  # API Key
├── .gitignore
├── requirements.txt
├── config.py             # 读 .env，提供配置 (~10行)
├── tools.py              # 4 个工具的定义 + 执行 (~80行)
├── agent.py              # Agent 决策核心 (~100行)
└── app.py                # Flask 入口 + 路由 (~50行)
```

### 职责划分

| 文件 | 职责 |
|------|------|
| `config.py` | 读 `.env`，暴露 `DEEPSEEK_API_KEY` 等配置 |
| `tools.py` | 4 个工具的 JSON Schema 定义 + 工具执行函数 |
| `agent.py` | 调 DeepSeek API、Function Calling 循环、对话记忆管理 |
| `app.py` | Flask 路由（`/api/ai/agent/chat`、`/health`），接收请求调 agent |

### 依赖方向（单向）

```
app.py → agent.py → tools.py
  ↓
config.py
```

---

## 六、文件清单

| 操作 | 文件 |
|------|------|
| 新建 | `ai-service/.env` |
| 新建 | `ai-service/.gitignore` |
| 新建 | `ai-service/requirements.txt` |
| 新建 | `ai-service/config.py` |
| 新建 | `ai-service/tools.py` |
| 新建 | `ai-service/agent.py` |
| 新建 | `ai-service/app.py` |
| 新建 | `aishoesrecommend/src/main/java/com/hubayi/aishoesrecommend/client/AiAgentClient.java` |
| 修改 | `aishoesrecommend/src/main/java/com/hubayi/aishoesrecommend/controller/ShoeProductController.java` |
| 修改 | `aishoesrecommend/src/main/java/com/hubayi/aishoesrecommend/service/ShoeProductService.java` |
| 重写 | `aishoesrecommend/src/main/resources/static/index.html` |

---

## 七、开发顺序

| 步骤 | 内容 | 验证方式 |
|------|------|----------|
| 1 | 创建 `requirements.txt` | `pip install -r requirements.txt` 无报错 |
| 2 | 创建 `.env` | Python 能读到 key |
| 3 | 写 `config.py` | 打印 key 非空 |
| 4 | 写 `tools.py` | 单独运行，工具函数输出正确 |
| 5 | 写 `agent.py` | 单独运行，发一条消息能收到 AI 回复 |
| 6 | 写 `app.py` | `curl localhost:5000/health` 返回 ok |
| 7 | 端到端测试 | `curl` 发消息，Agent 返回推荐结果 |
| 8 | 创建 Java `AiAgentClient.java` | 单元测试调通 |
| 9 | 修改 Java Controller/Service | Postman 测试 `/api/ai/chat` |
| 10 | 重写 `index.html` 对话界面 | 浏览器里完成一次对话推荐 |
| 11 | 错误降级测试 | 关掉 Python 服务，前端正常提示 |

---

## 八、技术约束

- Python Agent 单文件不超过 150 行，拆模块不拆子包
- 使用 DeepSeek Function Calling（兼容 OpenAI tool_use 格式）
- 对话历史内存存储，不引入 Redis/数据库
- 先做普通 JSON 返回，不做流式输出（SSE）
- 商品数据由 Java 传入，Agent 不直连数据库
- API Key 放 `.env`，`.env` 加入 `.gitignore`
