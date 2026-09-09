# AI 鞋类智能推荐 Agent

> **一个能自主决策的 AI 商品推荐系统** — 用户用自然语言描述需求，AI 自主调用 5 个工具搜索商品、分析穿搭、追问偏好、对比鞋款，最终给出带评分和理由的个性化推荐。

[![Spring Boot](https://img.shields.io/badge/Spring_Boot-4.0.6-6DB33F?logo=springboot)](https://spring.io/projects/spring-boot)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2.0-1C3C3C?logo=langchain)](https://langchain-ai.github.io/langgraph/)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-API-4D6BFE)](https://platform.deepseek.com/)
[![Redis](https://img.shields.io/badge/Redis-7-FF4438?logo=redis)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](https://docs.docker.com/compose/)

---

## 和普通 AI 问答有什么区别？

- **数据**：普通 AI 聊天用通用知识，可能推荐不存在的鞋；本项目用真实 MySQL 数据库，推荐的都是有库存的商品
- **交互**：普通 AI 一问一答，被动回复；本项目多轮对话，AI 主动追问缩小范围
- **决策**：普通 AI 用户告诉系统做什么；本项目 AI 自己决定调哪个工具、用哪些参数（ReAct Agent）
- **结果**：普通 AI 纯文本；本项目结构化商品卡片 + 匹配度评分 + 推荐理由 + 追问建议
- **可观测**：普通 AI 黑盒；本项目工具调用耗时、Token 消耗、P50/P95 延迟全链路追踪

---

## 系统架构

```
用户浏览器 (Vue 3 + SSE 流式消费)
    │  HTTP / SSE
Java Spring Boot (端口 8080)
  ├─ Controller 层：REST API + SSE 透传
  ├─ Service 层：业务逻辑
  ├─ DAO 层：JdbcTemplate 直连 MySQL
  ├─ AiAgentClient：调 Python Agent
  └─ static/：前端页面
    │  HTTP (内网)
Python FastAPI (端口 5000)
  ├─ LangGraph ReAct Agent
  ├─ 5 个工具（闭包注入，线程安全）
  ├─ ShoeRetriever：语义检索（带缓存）
  ├─ KnowledgeBase：三层 RAG（BM25 + 向量混合检索）
  └─ TraceContext：链路追踪
    │  HTTP
DeepSeek API (deepseek-chat)

共享基础设施：
  MySQL 8.0 ── 商品/用户/对话/反馈
  Redis 7    ── 对话记忆 + Session 共享
  SQLite     ── Agent 链路追踪数据
```

### 为什么分成 Java + Python 两个服务？

Java/Spring Boot 做 Web CRUD 最成熟、类型安全；Python 做 AI Agent 生态最好，LangChain 和 SentenceTransformer 全是 Python first。两个服务各用各的生态，内网通信延迟小于 5ms。

---

## Agent 工作流程

```
用户: "扁平足想找缓震跑鞋，预算500"
  ↓
Agent: Thought → 用户扁平足，先查选鞋知识
  ↓
Action → search_knowledge("扁平足 跑鞋 选购")
  ↓
Observation → "扁平足需要稳定支撑型跑鞋，避免过度内旋..."
  ↓
Agent: Thought → 基础清楚了，搜支撑型跑鞋
  ↓
Action → search_products(keyword="稳定支撑", category="跑鞋", max_price=500)
  ↓
Observation → 返回 5 款匹配商品
  ↓
Agent: 信息够了，组织推荐语（附评分 + 理由 + 追问建议）
```

**关键**：Agent 不是事先写好的 if-else 流程——它自己决定何时调哪个工具、用什么参数。这个决策循环（思考→行动→观察→再思考）由 LangGraph 驱动。

---

## 项目结构

```
AI鞋类商品推荐助手/
├── ai-service/                         # Python AI Agent 服务
│   ├── main.py                         # FastAPI 入口 + SSE 流式端点 + 统计 API
│   ├── agent.py                        # LangGraph ReAct Agent 核心 + Redis 对话记忆
│   ├── tools.py                        # 5 个工具定义（闭包注入，线程安全）
│   ├── retriever.py                    # 商品语义检索器（text2vec + 余弦相似度 + 缓存）
│   ├── knowledge_base.py               # 三层 RAG 知识库（BM25 + 向量 + RRF 融合）
│   ├── trace.py                        # Agent 链路追踪（SQLite，耗时/Token/首字延迟）
│   ├── scoring.py                      # 推荐评分：系统计算（非 LLM 编造）+ 可解释加分明细
│   ├── fusion.py                       # RRF 分数融合（归一化后再比阈值，见技术亮点 2）
│   ├── db.py                           # Python 直连 MySQL/Redis（架构 A）+ 商品缓存 TTL 300s
│   ├── reply_parser.py                 # Agent 回复解析（纯函数、无 IO，可单测）
│   ├── eval_dataset.py                 # 30 条 Agent 行为评测用例（5 种意图）
│   ├── eval_engine.py                  # Agent 行为评测（成功率/步数/工具准确率/影子测试）
│   ├── eval_catalog.py                 # 15 款标注商品目录
│   ├── eval_retrieval_dataset.py       # 22 条检索标注用例（相关项分级 2/1）
│   ├── eval_retrieval.py               # 离线检索评测（Recall@K / MRR / NDCG@K，5 策略消融）
│   ├── schemas.py / config.py          # Pydantic 模型 / 环境变量
│   └── tests/                          # 49 个 pytest 单测（评分/融合/BM25/过滤/反馈权重/解析）
│   ├── knowledge/                      # 鞋类专业知识（6 个领域，40 主块 + 54 子块）
│   │   ├── 01-材质科技.md    ├── 02-足型选购.md
│   │   ├── 03-运动场景.md    ├── 04-品牌定位.md
│   │   ├── 05-尺码指南.md    └── 06-保养清洁.md
│   └── requirements.txt
│
├── aishoesrecommend/                   # Java Spring Boot 后端
│   └── src/main/java/com/hubayi/aishoesrecommend/
│       ├── controller/
│       │   ├── ShoeProductController   # 商品 + AI 对话入口 + 用户画像
│       │   ├── UserController          # 注册/登录（BCrypt + Session）
│       │   ├── FavoriteController      # 收藏管理（JOIN 商品表）
│       │   ├── FeedbackController      # 推荐反馈（赞/踩）
│       │   ├── AiChatHistoryController # 对话历史持久化与多对话管理
│       │   └── AdminProductController  # 管理员 CRUD（权限校验）
│       ├── client/AiAgentClient        # 调 Python Agent（SSE 透传 + 降级）
│       ├── dao/    # JdbcTemplate 数据访问层（5 个 DAO）
│       ├── entity/ # 实体类（user/shoe_product/favorite/ai_chat_history/ai_feedback）
│       ├── service/ # 业务逻辑层
│       └── common/Result.java          # 统一响应 {code, message, data}
│   └── src/main/resources/
│       ├── sql/init.sql                # 建表 + 种子数据
│       └── static/                     # 前端（Vue 3 CDN，零构建工具）
│           ├── index.html              # 主页（AI 对话 + 商品浏览 + 用户画像 + 管理后台）
│           ├── login.html / register.html / profile.html
│           └── admin/stats.html        # 可观测性看板（Chart.js）
│
├── docker-compose.yml                  # 四服务编排（MySQL + Redis + Python + Java）
├── ai-service/Dockerfile               # Python 镜像（pip install + 模型预下载）
├── aishoesrecommend/Dockerfile         # Java 多阶段构建（Maven → JRE）
├── docker-init.sql                     # 容器首次启动自动初始化
└── README.md
```

---

## 快速启动

### 方式 A：Docker Compose（一键启动）

```bash
cp .env.example .env          # 编辑填入 MySQL 密码和 DeepSeek API Key
docker compose up -d           # 启动 MySQL + Redis + Python + Java
# 浏览器打开 http://localhost:8080/login.html
```

首次构建会自动下载 text2vec-base-chinese 模型（约 400MB），之后缓存在镜像内不需要重新下载。管理员默认账号 admin / 123456。

### 方式 B：手动启动（开发调试）

前提：JDK 17+、Python 3.11+、MySQL 8.0+、Maven 3.9+、Redis 7+。

```bash
# 1. 初始化数据库
mysql -u root -p < aishoesrecommend/src/main/resources/sql/init.sql

# 2. 启动 Redis（Docker 一行起）
docker run -d --name redis -p 6379:6379 redis:7-alpine

# 3. 启动 Python Agent
cd ai-service
pip install -r requirements.txt
cp .env.example .env   # 编辑填入 DeepSeek API Key
python main.py

# 4. 启动 Java 后端
cd aishoesrecommend
mvn spring-boot:run -DDB_PASSWORD=你的数据库密码
```

浏览器打开 `http://localhost:8080/login.html`。管理员：在数据库中将用户的 `role` 字段设为 `admin`。

---

## 技术亮点

### 1. ReAct Agent — 5 工具自主编排

Agent 自己决定何时调哪个工具、用什么参数，不是写死的 if-else。5 个工具通过闭包注入创建，多用户并发时各自的数据互不干扰。工具调用防重试机制：描述层引导"已调 2 次无结果应停止"、空结果返回结构化信号 `{"empty": true}`、`recursion_limit=15` 硬终止、流式失败降级非流式。

### 2. 三层 RAG 混合检索

- Layer 1 深度解析：按 ## 标题分主块（40 个）+ ### 子块索引（54 个，命中子块返回完整父块），正则提取品牌/技术/足型标签
- Layer 2 混合检索：向量语义检索 + BM25 纯 Python 关键词检索（中文 bigram 分词，零依赖）→ RRF 按**名次**融合（0.6/0.4，免疫量纲差异）→ 重排序（同源最多 2 块）
- Layer 3 生成校验：confidence 三级（high/medium/low），system prompt 防幻觉双检规则（禁止编造 + 强制来源标注 + 置信度分级处理）

> **踩过的坑（已修，附回归测试）**：RRF 分数天然极小（k=60 时单路贡献 ≈ 1/60 ≈ **0.0167**），
> 初版直接把融合分和固定阈值 `0.35` 比较 → **所有结果都被丢弃，知识库整体失效**。
> 修法：融合后先按 max 归一化到 0-1（rank0 = 1.0）再比阈值，并补了回归测试防止被改回去。

### 3. 全链路可观测性

每次 Agent 调用自动记录到 SQLite（traces.db）：trace_id、timestamp、duration_ms、first_token_ms、tool_calls(JSON)、tokens_input/output、error。前端 Chart.js 看板展示 P50/P95/P99 延迟分位数、每小时请求量、工具调用分布、每日 Token 趋势、最近 50 条明细表。Token 估算中文按 1.5 字符/token，误差 ±15%。

### 4. 量化评测体系

30 条标准用例覆盖 5 种意图（搜索/知识/穿搭/对比/追问），Python 脚本一键跑。当前指标：任务成功率 90%、工具调用准确率 86.7%、平均推理 2.5 步/次。知识/穿搭/对比三个意图 100% 成功率。影子测试：Agent 57% 返回结构化商品 vs 裸 LLM 0%。

### 5. 流式 SSE 三跳全通

Python `astream_events v2` 产生流 → Java HttpURLConnection 逐行透传（不用 RestTemplate，避免缓冲）→ 浏览器 `fetch() + ReadableStream` 逐字渲染 + 工具状态标签推送。Python 异常时降级 `agent.invoke()` 全量返回。

### 6. Redis 高并发分层设计

- Python 对话记忆从内存 dict 迁移 Redis String（pickle 序列化，TTL 24h），多 worker 共享 + 重启不丢。降级策略：Redis 连接失败自动回退内存 dict
- Java Session 从 Tomcat 内存迁 Spring Session Redis，多实例共享 + 重启不丢
- 向量索引缓存（get_retriever），double-check 锁防止重复建索引

### 7. 对话记忆三层架构

MySQL 持久化（永不丢）+ Redis 热数据（多 worker 共享）+ localStorage 保持当前对话 ID（刷新不丢）。两段截断防上下文膨胀：Java 端取最近 20 条 + Python 端每轮成对裁剪。

### 8. 三层容灾降级

SSE 流式失败 → `agent.invoke()` 非流式 → 连接超时推降级 SSE → 前端 fetch 失败切 `/api/ai/chat`，每层兜底不连锁。

### 9. 推荐评分：系统计算，不是 LLM 编造

分数由 `scoring.score_product` 用可解释的特征加权算出，**LLM 只把分数翻译成推荐理由，不负责生成分数**——
从根上杜绝"LLM 自己编个 95 分"。LLM 打分不可复现、不可解释、无法离线评测，这是刻意的设计取舍。

| 特征 | 分值 |
|---|---|
| 基础分 | 55（进入候选集即具备基本相关度） |
| 品类命中 | +15 |
| 品牌命中 | +10 |
| 性别匹配 | +5 |
| 预算内 | +10（超预算按比例扣，最多 -30） |
| query 属性词重叠 | +3/词 |
| 知识标签命中 | +2/个 |
| 历史反馈修正 | ×20 后**硬夹到 ±8** |

用户反馈走**贝叶斯平滑（m-estimate）**：`p_hat = (likes + α·μ) / (n + α)`，再减全局均值 μ 得到相对偏好。

- **冷启动数学上安全**：n=0 时 `p_hat = μ` → 权重 0 → 评分退化为纯内容分，不会因"只被点过一次"就把商品顶到第一。
- **封顶 ±8 是刻意的**：内容匹配永远是主信号，反馈只是修正项。若反馈可无限放大，一条误点就能把不相关的鞋推到首位。

---

## 数据库设计（ER 概要）

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

## 界面

浏览器访问 `http://localhost:8080` 登录后体验。

- AI 智能推荐：自然语言对话 + 商品推荐卡片 + 追问标签 + 反馈按钮
- 全部鞋款：筛选浏览 + 玻璃态卡片 + 收藏
- 我的画像：品牌偏好 + 品类分布 + 收藏均价 + 风格标签 + 反馈统计
- 可观测性看板：`/admin/stats.html`，Agent 调用统计

---

## 评测

两套评测，回答的是不同问题。

### A. Agent 行为评测 —— "有没有调对工具、几步完成"

```bash
cd ai-service
python eval_engine.py          # 全量 30 条
python eval_engine.py --fast   # 快测 10 条
```

结果自动存入 `traces.db → eval_runs`，看板可看历史对比。当前：任务成功率 90%、工具调用准确率 86.7%、平均 2.5 步/次。

### B. 离线检索评测 —— "召回了哪些、排第几"

```bash
python eval_retrieval.py       # 22 条标注用例 × 5 种排序策略消融
pytest tests/ -q               # 49 个单测
```

**不调 LLM，纯函数，秒级跑完，可进 CI。** 固定 15 款商品目录 + 人工标注 ground truth（相关项分级 2=高相关 / 1=部分相关），
**与生产共用同一份代码**（`fusion.rrf_fuse`、`scoring.score_product`），避免"测的是复刻件不是产品"。

| 策略 | R@1 | NDCG@5 | R@5 | 首位相关通过率 |
|---|---|---|---|---|
| rule（**现行生产**） | 0.287 | 0.503 | — | 59.1% |
| bm25 | 0.542 | — | — | — |
| **rrf + score（提出）** | — | **0.842** | 0.861 | **86.4%** |

**结论照实说**：现行生产的纯规则 ranker 在**语义查询上是最差的一环**，这是测出来的不是猜的。
约束类查询（"600 以内""女款"）五种策略指标完全相同 → 结构化约束由**过滤**解决，不该让排序器背锅。
**局限**：22 条样本量偏小，绝对值精度有限，策略间相对比较才有效。

---

## 技术栈

- 前端：Vue 3 CDN + 原生 CSS / SSE 流式消费
- Web 后端：Spring Boot 4 + JdbcTemplate + Spring Session Redis
- AI 引擎：FastAPI + LangGraph ReAct Agent
- LLM：DeepSeek（兼容 OpenAI 协议）
- 语义检索：SentenceTransformer `text2vec-base-chinese`
- 数据库：MySQL 8.0（业务数据）+ SQLite（追踪数据）
- 缓存/会话：Redis 7（对话记忆 + Session 共享）
- 部署：Docker Compose（MySQL + Redis + Python + Java）

---

## 已知缺口与下一步

按"会不会真的出问题"排序，不粉饰。

**安全 / 生产就绪**

- **AI 接口无限流（未做）**：`/api/ai/chat`、`/api/ai/chat/stream` 已做 session 鉴权（未登录返回 401），
  但**没有按用户限流**。LLM 是付费资源，这是上线前必须补的第一件事。
- **鉴权是逐方法手写的（根因）**：本项目未引入 Spring Security，鉴权靠每个方法自己检查 session，
  漏一个是必然不是偶然——这两个 AI 端点原先就是漏网之鱼。生产做法应加**统一拦截器**，
  把鉴权从"记得写"变成"框架保证"。
- **SSE 断连清理是异常驱动的**：客户端断开后靠下一次 `write` 抛 IOException 才触发 `disconnect()`，
  不是主动事件监听。更严谨应上 Servlet 3.1 `WriteListener`。

**效果 / 数据**

- **排序信号待升级**：离线评测显示 rrf+score（NDCG@5 **0.842**）优于现行纯规则（0.503），尚未切到生产。
- **样本量偏小**：检索评测仅 22 条标注用例，绝对值精度有限，需扩到数百条才有置信度。
- **无真实用户数据**：ground truth 是人工标注而非真实点击。上线需补曝光/点击埋点，
  用真实点击率替换手工标注。

**规模 / 工程**

- 引入 FAISS/Milvus 替代内存向量索引（商品超 1000 条时）
- 热门查询缓存（搜索参数 hash → 结果，TTL 5 分钟）
- MCP 协议标准化工具接口（当前是内嵌 HTTP 调用）
