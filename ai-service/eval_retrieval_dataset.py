"""检索评测标注集 —— 带 ground truth 的商品相关性标注。

和 eval_dataset.py 的区别（很重要，面试会问）：
  - eval_dataset.py 测的是 **Agent 行为**（有没有调对工具、回复里有没有出现关键词），
    需要真调 LLM，慢、贵、不确定，且"成功"的判定是一串 or 条件，几乎不可能失败。
  - 本文件测的是 **检索/排序质量**：给定 query，正确答案是哪几个商品 id。
    完全离线、确定性、可进 CI，能算 Recall@K / MRR / NDCG@K，
    也能做消融对比（BM25 vs 向量 vs RRF vs RRF+评分）。

相关性分级（graded relevance，供 NDCG 用）：
  2 = 高度相关，用户看到会直接考虑下单
  1 = 部分相关，同品类或沾边，排前面不算错但不是最优解
  未列出 = 不相关

标注方法：对 EVAL_PRODUCTS 这 15 款鞋逐条人工判定。
标注是主观的，这里的诚实说法是"单人标注、无交叉校验"，
不宣称是黄金标准；但它固定下来之后，
不同检索策略之间的**相对高低**是可靠的——消融对比要的就是相对值。
"""

# 评测用固定商品目录（eval_engine 也从这里取，避免两套数据漂移）
from eval_catalog import PRODUCTS as EVAL_PRODUCTS  # noqa: E402

# ---------------------------------------------------------------------------
# 语义检索用例：靠文本语义就该召回，不依赖结构化过滤
# ---------------------------------------------------------------------------
RETRIEVAL_CASES = [
    {
        "id": "R01", "query": "缓震好的跑鞋",
        "relevance": {1: 2, 2: 2, 7: 2, 11: 2, 13: 2, 3: 1},
        "note": "5 款主打缓震的跑鞋为高相关；Kayano 是支撑型，同品类但非缓震导向",
    },
    {
        "id": "R02", "query": "扁平足适合什么跑鞋",
        "relevance": {3: 2, 11: 1},
        "note": "Kayano 描述里直写扁平足/过度内旋；1080 宽楦稳定沾边",
    },
    {
        "id": "R03", "query": "宽脚穿的跑鞋",
        "relevance": {11: 2},
        "note": "只有 1080v13 明确 2E/4E 宽楦",
    },
    {
        "id": "R04", "query": "高足弓需要软一点的鞋底",
        "relevance": {13: 2, 7: 1, 2: 1},
        "note": "Nimbus 直写高足弓+软底；Cloudmonster/Ultraboost 软弹沾边",
    },
    {
        "id": "R05", "query": "Nike 的篮球鞋",
        "relevance": {6: 2},
        "note": "目录里唯一的篮球鞋",
    },
    {
        "id": "R06", "query": "Vans 板鞋",
        "relevance": {4: 2, 14: 1},
        "note": "Old Skool 是 Vans 板鞋；Speedcat 同品类不同品牌",
    },
    {
        "id": "R07", "query": "夏天透气不闷脚的鞋",
        "relevance": {8: 2, 5: 1},
        "note": "Crocs 直写透气不闷脚夏天必备；帆布鞋次之",
    },
    {
        "id": "R08", "query": "百搭的帆布鞋",
        "relevance": {5: 2},
    },
    {
        "id": "R09", "query": "女生穿的休闲鞋",
        "relevance": {10: 2, 9: 1, 8: 1},
        "note": "Gazelle 是 female+休闲鞋双命中；Dunk Low 是 female 但归运动鞋",
    },
    {
        "id": "R10", "query": "比赛竞速穿的跑鞋",
        "relevance": {12: 2},
        "note": "Adizero SL 是目录里唯一竞速定位",
    },
    {
        "id": "R11", "query": "久站走路脚不累的鞋",
        "relevance": {15: 2, 8: 1},
        "note": "Go Walk 直写走路久站",
    },
    {
        "id": "R12", "query": "脚窄的人适合什么鞋",
        "relevance": {14: 2},
        "note": "Speedcat 直写窄脚瘦脚",
    },
    {
        "id": "R13", "query": "上班通勤穿的简约鞋",
        "relevance": {9: 2, 2: 1, 5: 1},
    },
    {
        "id": "R14", "query": "Adidas 跑鞋",
        "relevance": {2: 2, 12: 2, 10: 1},
        "note": "Ultraboost + Adizero 都是 Adidas 跑鞋；Gazelle 同品牌但非跑鞋",
    },
    {
        "id": "R15", "query": "长距离路跑的鞋",
        "relevance": {7: 2, 1: 1, 11: 1},
    },
    {
        "id": "R16", "query": "复古街头风格的鞋",
        "relevance": {4: 2, 6: 1, 10: 1, 14: 1},
    },
    {
        "id": "R17", "query": "厚底增高的鞋",
        "relevance": {10: 2},
    },
    {
        "id": "R18", "query": "洞洞鞋",
        "relevance": {8: 2},
    },
]

# ---------------------------------------------------------------------------
# 结构化约束用例：语义检索单独做不到，必须靠过滤 + 评分
# 这组用例存在的意义就是暴露"纯向量检索"的能力边界
# ---------------------------------------------------------------------------
CONSTRAINT_CASES = [
    {
        "id": "F01", "query": "600 以内的鞋",
        "filters": {"max_price": 600},
        "relevance": {8: 2, 5: 2, 4: 2, 15: 2},
        "note": "399/499/569/599 四款，纯语义检索无法感知价格",
    },
    {
        "id": "F02", "query": "1000 以内的 Adidas",
        "filters": {"max_price": 1000, "brand": "Adidas"},
        "relevance": {12: 2, 10: 2},
        "note": "Ultraboost 1099 超预算应被排除",
    },
    {
        "id": "F03", "query": "女款的鞋",
        "filters": {"gender": "女"},
        "relevance": {9: 2, 10: 2, 13: 2},
    },
    {
        "id": "F04", "query": "800 到 1200 的跑鞋",
        "filters": {"min_price": 800, "max_price": 1200, "category": "跑鞋"},
        "relevance": {1: 2, 2: 2, 3: 2, 11: 2},
        "note": "Cloudmonster 1299 / Nimbus 1290 超上限；Adizero 699 低于下限且属竞速跑鞋",
    },
]

# ---------------------------------------------------------------------------
# 无解用例：目录里根本没有的东西，正确行为是拒答而不是硬凑
# 注意：**不计入排序指标**。纯检索器按定义永远返回 top-k，
# 让它"返回空"是不公平的——拒答是 Agent 层（阈值 + prompt）的职责，
# 放在这里只是提醒后续做 Agent 级评测时别漏了这一类。
# ---------------------------------------------------------------------------
NO_ANSWER_CASES = [
    {"id": "N01", "query": "登山鞋要防滑耐磨的", "reason": "目录无登山鞋"},
    {"id": "N02", "query": "老爹鞋推荐一双", "reason": "目录无老爹鞋"},
    {"id": "N03", "query": "皮鞋配西装", "reason": "目录无正装皮鞋"},
]


def all_ranking_cases() -> list[dict]:
    """参与排序指标计算的全部用例（语义 + 结构化约束）。"""
    return RETRIEVAL_CASES + CONSTRAINT_CASES
