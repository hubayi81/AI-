# AI 鞋类智能导购 Agent 🏃

> **一个能自主决策的 AI 导购系统** — 用户用自然语言描述需求，AI 自主调用工具搜索商品、分析穿搭、追问偏好、对比鞋款，最终给出带评分和理由的个性化推荐。

[![Spring Boot](https://img.shields.io/badge/Spring_Boot-4.0.6-6DB33F?logo=springboot)](https://spring.io/projects/spring-boot)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2.0-1C3C3C?logo=langchain)](https://langchain-ai.github.io/langgraph/)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-API-4D6BFE)](https://platform.deepseek.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python)](https://www.python.org/)
[![Java](https://img.shields.io/badge/Java-17-ED8B00?logo=openjdk)](https://adoptium.net/)

---

## 🎯 和普通 AI 问答有什么区别？

| | 普通 AI 聊天 | 本项目 |
|---|---|---|
| **数据** | 通用知识，可能推荐不存在的鞋 | 真实数据库，推荐的都是有库存的商品 |
| **交互** | 一问一答，被动回复 | 多轮对话，AI 主动追问缩小范围 |
| **决策** | 用户告诉系统做什么 | AI 自己决定调哪个工具、用哪些参数 |
| **结果** | 纯文本 | 结构化商品卡片 + 匹配度评分 + 推荐理由 |
| **可观测** | 黑盒 | 工具调用耗时、Token 消耗全链路追踪 |

---

## 🏗️ 系统架构

```
用户浏览器 (Vue 3 + 玻璃态 UI)
    │  SSE 流式对话 / RESTful API
    ▼
┌─────────────────────────────────────────────┐
│  Java Spring Boot (端口 8080)                │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ Controller│ │ Service  │ │ DAO (JDBC)  │ │
│  │ 用户/商品 │ │ 业务逻辑 │ │ MySQL 交互  │ │
│  │ 收藏/反馈 │ │          │ │             │ │
│  └──────────┘ └──────────┘ └─────────────┘ │
│                                              │
│  AiAgentClient ── HTTP ──→ Python Agent 服务 │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│  Python FastAPI (端口 5000)                   │
│  ┌──────────────────────────────────────┐   │
│  │  LangGraph ReAct Agent                │   │
│  │                                       │   │
│  │  Thought → Action → Observation → ... │   │
│  │                                       │   │
│  │  工具集:                               │   │
│  │  🔍 search_products  语义搜索          │   │
│  │  👗 analyze_outfit   穿搭分析          │   │
│  │  ⚖️ compare_shoes    商品对比          │   │
│  │  ❓ ask_clarify      智能追问          │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  ┌────────────┐ ┌──────────┐ ┌───────────┐ │
│  │ 语义检索    │ │ 知识库   │ │ 链路追踪  │ │
│  │ text2vec   │ │ 鞋类知识 │ │ SQLite    │ │
│  └────────────┘ └──────────┘ └───────────┘ │
└─────────────────────────────────────────────┘
                    │
                    ▼
              DeepSeek API
```

### 为什么分成 Java + Python 两个服务？

| 考量 | 说明 |
|------|------|
| **技术栈匹配** | Java/Spring Boot 做 Web CRUD 最成熟；Python 做 AI Agent 生态最好（LangChain/LangGraph 全是 Python first） |
| **独立扩容** | Agent 调用 LLM 耗时数秒，和 Web 请求隔离，互不拖慢 |
| **无状态设计** | Agent 不持有数据库连接，商品数据由 Java 传入。Python 服务挂了不影响商品浏览 |

---

## 🔄 Agent 工作流程

```
用户: "脚宽跑步预算500，膝盖不太好"
  │
  ▼
Agent 分析需求 → 调 search_products(keyword="缓震宽楦", category="跑鞋", max_price=500)
  │
  ▼
返回 8 款匹配商品
  │
  ▼
Agent: 太多，需要缩小范围 → 调 ask_clarify("需要顶级缓震还是基础缓震？")
  │
  ▼
用户: "顶级缓震的"
  │
  ▼
Agent: 筛出 3 款 → 调 knowledge_base 查缓震科技 → 组织推荐语
  │
  ▼
返回: 推荐卡片（评分 + 理由 + 追问建议）+ "Gel-Kayano 30 采用 GEL 缓震胶..."
```

**关键**：Agent 不是我事先写好的 if-else 逻辑——它自己决定何时调工具、调哪个工具、用哪些参数。这是 Agent 和传统工作流的本质区别。

---

## 📂 项目结构

```
AI鞋类商品推荐助手/
├── ai-service/                         # Python AI Agent 服务
│   ├── main.py                         # FastAPI 入口 + SSE 流式端点
│   ├── agent.py                        # LangGraph ReAct Agent 核心 + 对话记忆
│   ├── tools.py                        # 4 个工具定义（闭包注入数据，线程安全）
│   ├── retriever.py                    # 商品语义检索器（text2vec + 余弦相似度）
│   ├── knowledge_base.py               # 鞋类知识库（Markdown 分块 + 语义检索）
│   ├── trace.py                        # Agent 链路追踪（工具耗时/Token 统计）
│   ├── schemas.py                      # Pydantic 请求/响应模型
│   ├── config.py                       # 环境变量读取
│   ├── knowledge/                      # 鞋类专业知识文档（6 个领域）
│   │   ├── 01-材质科技.md
│   │   ├── 02-足型选购.md
│   │   ├── 03-运动场景.md
│   │   ├── 04-品牌定位.md
│   │   ├── 05-尺码指南.md
│   │   └── 06-保养清洁.md
│   └── requirements.txt
│
├── aishoesrecommend/                   # Java Spring Boot 后端
│   └── src/main/java/com/hubayi/aishoesrecommend/
│       ├── controller/
│       │   ├── ShoeProductController   # 商品 + AI 对话入口
│       │   ├── UserController          # 注册/登录（BCrypt + Session）
│       │   ├── FavoriteController      # 收藏管理
│       │   ├── FeedbackController      # 推荐反馈（赞/踩）
│       │   ├── AiChatHistoryController # 对话历史持久化
│       │   └── AdminProductController  # 管理员 CRUD（权限校验）
│       ├── client/
│       │   └── AiAgentClient           # 调 Python Agent（流式 SSE 透传 + 降级）
│       ├── dao/                        # JdbcTemplate 数据访问层
│       ├── entity/                     # 实体类（ShoeProduct/User/Favorite/Feedback）
│       ├── service/                    # 业务逻辑层
│       └── common/Result.java          # 统一响应格式 {code, message, data}
│   └── src/main/resources/
│       ├── sql/init.sql                # 建表 + 示例数据
│       └── static/                     # 前端页面（纯 HTML + Vue 3 CDN）
│           ├── index.html              # 主页（AI 对话 + 商品浏览 + 管理后台）
│           ├── login.html / register.html / profile.html
│           └── admin/stats.html        # 管理统计页
│
├── AI鞋类推荐助手-需求文档.md           # 项目需求文档
└── README.md
```

---

## 🚀 快速启动

### 前提

- JDK 17+
- Python 3.11+
- MySQL 8.0+
- Maven 3.9+

### 1. 初始化数据库

```bash
mysql -u root -p < aishoesrecommend/src/main/resources/sql/init.sql
```

### 2. 启动 Python Agent 服务

```bash
cd ai-service
pip install -r requirements.txt

# 配置 DeepSeek API Key（第一次运行前）
cp .env.example .env   # 编辑 .env 填入你的 API Key

# 启动（首次运行会下载 text2vec-base-chinese 模型，约 400MB）
python main.py
# → AI Agent 服务启动：http://localhost:5000/docs
```

### 3. 启动 Java 后端

```bash
cd aishoesrecommend

# 配置数据库密码（二选一）
# 方式 A：IDEA 中 Run → Edit Configurations → VM options 添加：
#   -DDB_PASSWORD=你的数据库密码
# 方式 B：直接改 src/main/resources/application.yml 中的 password

mvn spring-boot:run
# → 后端启动：http://localhost:8080
```

### 4. 打开前端

浏览器访问 `http://localhost:8080/login.html`，注册账号后即可使用。

> 管理员功能：在数据库中将用户的 `role` 字段设为 `admin`，即可看到商品新增/编辑/删除功能。

---

## 🔧 技术亮点（面试深度）

### 1. Agent 不是黑盒 — 全链路追踪

每次 Agent 调用自动记录到 SQLite（`traces.db`），包含：

- **工具调用链**：哪个工具被调了？耗时多少？
- **首 Token 延迟**：流式输出第一个字多久出现？
- **Token 消耗估算**：输入/输出各多少 Token？

```
agent_traces 表:
┌──────────┬──────────────┬─────────┬───────────────┬──────────────────────┐
│ trace_id │ duration_ms  │ tool_calls              │ tokens_input/output  │
├──────────┼──────────────┼─────────────────────────┼──────────────────────┤
│ a1b2c3d4 │ 3421.5       │ [{"search_products":    │ 1850 / 420           │
│          │              │   89.2},                 │                      │
│          │              │  {"ask_clarify": 45.1}]  │                      │
└──────────┴──────────────┴─────────────────────────┴──────────────────────┘
```

### 2. 语义检索 × 知识库 — 双重 RAG

| 检索层 | 数据来源 | 用途 |
|--------|----------|------|
| **商品检索**（`retriever.py`） | Java 传入的商品列表 | 语义匹配 → 结构化过滤（两阶段） |
| **知识库**（`knowledge_base.py`） | `knowledge/*.md` 鞋类专业知识 | 按 `##` 标题分块，Agent 调工具时自动检索 |

两阶段过滤的设计理由：纯语义检索可能召回品类不匹配的商品（比如搜"跑步"召回了跑鞋和运动鞋配件），先用语义检索拿到候选集，再用 category/brand/gender/price 精确过滤，比纯语义或纯过滤都好。

### 3. 三层容灾降级

```
SSE 流式 ──失败──→ 非流式 JSON ──失败──→ "AI 暂不可用，请使用传统筛选"
（首选）           （自动降级）           （前端友好提示）
```

- **Agent 级**：`astream_events` 异常时 catch 后切 `agent.invoke()`
- **服务级**：Java `AiAgentClient` 捕获异常返回降级话术
- **前端级**：`checkAIHealth()` 检测 `/api/ai/health`，离线时显示提示条

### 4. 流式输出的体验设计

SSE 不仅是"逐字打字"，还推送**工具执行状态**：

```
用户发送 "脚宽跑步预算500"
  ↓
SSE: {"status": "正在为你搜索合适的鞋款…"}     ← 前端显示加载动画
SSE: {"token": "根据"}                          ← 逐字打字
SSE: {"token": "你"}                                      
SSE: {"token": "的"}                                      
SSE: {"status": ""}                             ← 工具执行结束，恢复正常
SSE: {"done": true, "results": [...],
      "followUps": ["有更便宜的吗？", ...]}
```

这样用户不会觉得"卡住了 5 秒"，而是清楚地知道 AI 在做什么。

### 5. 个性化画像系统

```java
// Java 端根据用户收藏计算画像，注入 System Prompt
String userContext = buildUserContext(session);
// → "该用户画像：偏好品牌 Nike、Adidas；偏好鞋类 跑鞋；平均收藏价位约 ¥680；共收藏 5 双鞋。"
```

画像以自然语言注入 System Prompt，Agent 做个性化推荐但不会刻意提「画像」两个字。设计考量：**收藏 = 用户主动行为，比浏览更可靠**。

### 6. 工具设计的工程考量

- **闭包注入**：`create_tools(products)` 每次请求创建新工具实例，商品数据通过闭包传入 → 多用户并发时不会读到彼此的数据
- **粒度控制**：4 个工具覆盖 4 种意图，不会太多（LLM 选择困难）也不会太少（功能不够）
- **幂等性**：`compare_shoes` 需要两个 ID 而非名称，避免同名商品歧义
- **容错**：`search_products` 无结果返回空数组而非报错，让 Agent 决定下一步（追问或放宽条件）

---

## 📊 数据库设计（ER 概要）

```
user                shoe_product          favorite
──────              ────────────          ────────
id (PK)             id (PK)               id (PK)
username            name                  user_id (FK → user)
password (BCrypt)   brand                 product_id (FK → shoe_product)
role (user/admin)   category              create_time
create_time         gender
                    price                 ai_chat_history
                    description           ──────────────
                    stock                 id (PK)
                    image_url             user_id (FK → user)
                    color                 conversation_id
                    size_range            role (user/ai)
                    create_time           content
                                          create_time
                    ai_feedback
                    ──────────
                    id (PK)
                    user_id (FK → user)
                    conversation_id
                    user_message
                    ai_reply
                    feedback (like/dislike)
                    create_time
```

---

## 🖼️ 界面预览

> 浏览器访问 `http://localhost:8080` 后登录即可体验。

**AI 智能导购**：自然语言对话 + 商品推荐卡片 + 追问标签 + 反馈按钮

**全部鞋款**：筛选浏览 + 玻璃态卡片 + 收藏（带粒子特效）+ 管理员增删改

**管理后台**：`/admin/stats.html` — Agent 调用统计看板

---

## 📝 开发笔记

### 为什么用 `create_react_agent` 而不是手写 Agent 循环？

LangGraph 的 `create_react_agent` 封装了 ReAct 循环（Thought → Action → Observation → Thought → ...），自动处理工具调用的 JSON 解析、结果回传、循环终止判断。手写也可以（一个 while 循环 + if 判断），但你需要处理的边界情况——工具调用格式异常、最大循环次数、历史消息拼接顺序——LangGraph 都已经处理好了。

### 为什么 Agent 不直连数据库？

Agent 是无状态服务。商品数据由 Java 查好后通过 HTTP 传入，Agent 只用内存中的数据做推理。这样 Python 服务可以随意重启、水平扩容，不依赖数据库连接。代价是每次请求传全量商品——如果商品库 10 万+ 条就需要引入向量数据库替代内存检索。

### 知识库为什么按 `##` 分块而不是固定字数？

每个 `##` 标题是一个独立的知识点（如"扁平足的选鞋要点"），按标题分块能保证语义完整——不会把一个知识点切成两半。固定字数分块虽然实现简单，但容易在语义边界处截断。

---

## 🔮 待优化

- [ ] 引入 FAISS/Milvus 替代内存向量索引（商品 > 1000 时需要）
- [ ] 引入 Redis 做会话记忆持久化（当前服务重启丢记忆）
- [ ] 基于反馈数据（like/dislike）做自动化评估（MRR / NDCG）
- [ ] MCP 协议标准化工具接口（当前是 HTTP 内嵌工具）
- [ ] Docker Compose 一键部署

---

## 📄 技术栈一览

| 层 | 技术 | 用途 |
|----|------|------|
| **前端** | Vue 3 CDN + 原生 CSS | 玻璃态 UI，SSE 流式接收 |
| **Web 后端** | Spring Boot 4 + JdbcTemplate | RESTful API，用户系统，商品 CRUD |
| **AI 引擎** | FastAPI + LangGraph | Agent 决策循环，工具调用编排 |
| **LLM** | DeepSeek（兼容 OpenAI 协议）| Function Calling / Tool Use |
| **语义检索** | SentenceTransformer `text2vec-base-chinese` | 商品 & 知识库语义匹配 |
| **数据库** | MySQL 8.0 | 业务数据（用户/商品/收藏/反馈） |
| **追踪** | SQLite（Python 标准库）| Agent 调用链路零运维追踪 |
| **安全** | BCrypt + Session | 密码加密，会话管理 |
