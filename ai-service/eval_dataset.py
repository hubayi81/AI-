"""
评测数据集 — 30 条测试用例，覆盖 5 种 Agent 意图。

每条用例包含：
- query: 用户输入
- intent: 意图类型（search / knowledge / outfit / compare / clarify）
- expected_tools: 期望 Agent 调用的工具（至少命中一个即算工具选择正确）
- min_results: 期望最少返回几个商品（0 表示不要求）
- key_terms: 回复中应出现的术语（用于验证 Agent 是否用了正确知识）
"""

EVAL_CASES = [
    # ═══ 意图：search_products — 基础商品搜索（10 条）═══
    {
        "id": "S01",
        "query": "推荐一双缓震好的跑鞋，预算 500 以内",
        "intent": "search",
        "expected_tools": ["search_products"],
        "min_results": 2,
        "key_terms": ["缓震", "跑鞋"],
    },
    {
        "id": "S02",
        "query": "有没有适合夏天穿的透气运动鞋",
        "intent": "search",
        "expected_tools": ["search_products"],
        "min_results": 1,
        "key_terms": ["透气", "运动鞋"],
    },
    {
        "id": "S03",
        "query": "我想买一双 Nike 的篮球鞋",
        "intent": "search",
        "expected_tools": ["search_products"],
        "min_results": 1,
        "key_terms": ["Nike", "篮球鞋"],
    },
    {
        "id": "S04",
        "query": "女生穿的休闲鞋，300 以内",
        "intent": "search",
        "expected_tools": ["search_products"],
        "min_results": 1,
        "key_terms": ["休闲鞋"],
    },
    {
        "id": "S05",
        "query": "帮我找一双轻便的帆布鞋",
        "intent": "search",
        "expected_tools": ["search_products"],
        "min_results": 1,
        "key_terms": ["帆布鞋"],
    },
    {
        "id": "S06",
        "query": "推荐一双登山鞋，要防滑耐磨",
        "intent": "search",
        "expected_tools": ["search_products"],
        "min_results": 1,
        "key_terms": ["登山", "防滑"],
    },
    {
        "id": "S07",
        "query": "有没有 Crocs 的洞洞鞋",
        "intent": "search",
        "expected_tools": ["search_products"],
        "min_results": 1,
        "key_terms": ["Crocs"],
    },
    {
        "id": "S08",
        "query": "给我推荐一款老爹鞋，预算 600",
        "intent": "search",
        "expected_tools": ["search_products"],
        "min_results": 1,
        "key_terms": ["老爹鞋"],
    },
    {
        "id": "S09",
        "query": "要一双板鞋，Vans 的",
        "intent": "search",
        "expected_tools": ["search_products"],
        "min_results": 1,
        "key_terms": ["Vans", "板鞋"],
    },
    {
        "id": "S10",
        "query": "Adidas 跑鞋 800 以内有哪些",
        "intent": "search",
        "expected_tools": ["search_products"],
        "min_results": 1,
        "key_terms": ["Adidas", "跑鞋"],
    },

    # ═══ 意图：search_knowledge — 专业知识检索（6 条）═══
    {
        "id": "K01",
        "query": "扁平足应该选什么样的跑鞋",
        "intent": "knowledge",
        "expected_tools": ["search_knowledge"],
        "min_results": 0,
        "key_terms": ["支撑", "稳定", "足弓"],
    },
    {
        "id": "K02",
        "query": "EVA 和 Boost 中底有什么区别",
        "intent": "knowledge",
        "expected_tools": ["search_knowledge"],
        "min_results": 0,
        "key_terms": ["EVA", "Boost"],
    },
    {
        "id": "K03",
        "query": "碳板跑鞋适合新手吗",
        "intent": "knowledge",
        "expected_tools": ["search_knowledge"],
        "min_results": 0,
        "key_terms": ["碳板", "新手"],
    },
    {
        "id": "K04",
        "query": "高足弓的人怎么选鞋",
        "intent": "knowledge",
        "expected_tools": ["search_knowledge"],
        "min_results": 0,
        "key_terms": ["缓震", "高足弓"],
    },
    {
        "id": "K05",
        "query": "Gore-Tex 防水鞋夏天穿会闷脚吗",
        "intent": "knowledge",
        "expected_tools": ["search_knowledge"],
        "min_results": 0,
        "key_terms": ["Gore-Tex", "透气"],
    },
    {
        "id": "K06",
        "query": "网面跑鞋怎么清洗",
        "intent": "knowledge",
        "expected_tools": ["search_knowledge"],
        "min_results": 0,
        "key_terms": ["清洗", "网面"],
    },

    # ═══ 意图：analyze_outfit — 穿搭分析（4 条）═══
    {
        "id": "O01",
        "query": "周末约会穿白色连衣裙，搭配什么鞋好",
        "intent": "outfit",
        "expected_tools": ["analyze_outfit"],
        "min_results": 0,
        "key_terms": ["约会", "搭配"],
    },
    {
        "id": "O02",
        "query": "上班通勤穿西装裤，想配一双简约的鞋",
        "intent": "outfit",
        "expected_tools": ["analyze_outfit"],
        "min_results": 0,
        "key_terms": ["通勤", "简约"],
    },
    {
        "id": "O03",
        "query": "穿牛仔裤逛街，推荐一双百搭的运动鞋",
        "intent": "outfit",
        "expected_tools": ["analyze_outfit"],
        "min_results": 1,
        "key_terms": ["逛街", "百搭"],
    },
    {
        "id": "O04",
        "query": "夏天穿短裤配什么鞋比较好看",
        "intent": "outfit",
        "expected_tools": ["analyze_outfit"],
        "min_results": 0,
        "key_terms": ["夏天", "短裤"],
    },

    # ═══ 意图：compare_shoes — 商品对比（4 条）═══
    {
        "id": "C01",
        "query": "帮我对比一下第 1 款和第 3 款",
        "intent": "compare",
        "expected_tools": ["compare_shoes"],
        "min_results": 0,
        "key_terms": [],
    },
    {
        "id": "C02",
        "query": "Air Max 和 Ultraboost 哪个更适合跑步",
        "intent": "compare",
        "expected_tools": ["search_products", "compare_shoes"],
        "min_results": 0,
        "key_terms": [],
    },
    {
        "id": "C03",
        "query": "这两双鞋帮我对比一下优缺点",
        "intent": "compare",
        "expected_tools": ["compare_shoes"],
        "min_results": 0,
        "key_terms": [],
    },
    {
        "id": "C04",
        "query": "Nike 跑鞋和 Adidas 跑鞋哪个好",
        "intent": "compare",
        "expected_tools": ["search_products"],
        "min_results": 1,
        "key_terms": ["Nike", "Adidas"],
    },

    # ═══ 意图：ask_clarify — 模糊需求追问（6 条）═══
    {
        "id": "Q01",
        "query": "推荐一双鞋",
        "intent": "clarify",
        "expected_tools": ["ask_clarify"],
        "min_results": 0,
        "key_terms": [],
    },
    {
        "id": "Q02",
        "query": "我想买鞋",
        "intent": "clarify",
        "expected_tools": ["ask_clarify"],
        "min_results": 0,
        "key_terms": [],
    },
    {
        "id": "Q03",
        "query": "有没有好穿的鞋",
        "intent": "clarify",
        "expected_tools": ["search_products"],
        "min_results": 1,
        "key_terms": [],
    },
    {
        "id": "Q04",
        "query": "帮我看看运动鞋",
        "intent": "clarify",
        "expected_tools": ["search_products"],
        "min_results": 1,
        "key_terms": ["运动鞋"],
    },
    {
        "id": "Q05",
        "query": "不知道买什么鞋好",
        "intent": "clarify",
        "expected_tools": ["ask_clarify"],
        "min_results": 0,
        "key_terms": [],
    },
    {
        "id": "Q06",
        "query": "最便宜的鞋是哪双",
        "intent": "search",
        "expected_tools": ["search_products"],
        "min_results": 1,
        "key_terms": [],
    },
]
