"""推荐评分：系统计算，非 LLM 编造。

基于可解释的特征加权：
  - 品类命中
  - 品牌命中
  - 性别匹配
  - 预算内接近度（price 越接近预算区间越优）
  - 关键词/知识属性重叠（缓震、支撑、足型等标签）
  - 历史反馈修正（👍/👎 贝叶斯平滑后的相对偏好，冷启动为 0）
LLM 只负责解释这个分数，不负责生成它。
"""

# 反馈修正的放大系数与封顶。
# weight 取值约 (-0.5, 0.5)，×20 后理论范围 (-10, 10)，再硬夹到 ±8：
# 反馈只做"同档位内微调"，不允许把一个明显不匹配的商品顶上来——
# 内容匹配度永远是主信号，用户反馈是修正项而不是决定项。
FEEDBACK_K = 20.0
FEEDBACK_CAP = 8.0

# 常见鞋类/属性关键词，用于 query 与商品文本的属性重叠匹配
ATTRIBUTE_KEYWORDS = [
    "缓震", "支撑", "透气", "防水", "耐磨", "轻量", "宽楦", "窄楦",
    "扁平足", "高足弓", "宽脚", "窄脚", "篮球", "跑步", "通勤",
    "登山", "越野", "竞速", "健身", "休闲",
]


def score_product(
    query: str,
    product: dict,
    *,
    category: str = "",
    brand: str = "",
    gender: str = "",
    min_price: float = 0,
    max_price: float = 0,
    knowledge_tags: list[str] | None = None,
    feedback_weight: float = 0.0,
) -> float:
    """返回 0-100 的匹配度评分（系统计算，可解释）。

    feedback_weight: 该商品的历史反馈偏好权重（见 db.load_feedback_weights），
                     无反馈数据时为 0，此时评分完全等价于纯内容匹配。
    """
    score = 55.0  # 基础分：进入候选集即至少具备基本相关度

    # 1) 品类命中
    if category and product.get("category", "").strip().lower() == category.strip().lower():
        score += 15

    # 2) 品牌命中
    if brand:
        if product.get("brand", "").strip().lower() == brand.strip().lower():
            score += 10

    # 3) 性别匹配
    if gender:
        g_map = {"男": "male", "女": "female", "通用": "unisex", "中性": "unisex"}
        g = g_map.get(gender, gender)
        if product.get("gender", "") == g:
            score += 5

    # 4) 预算接近度
    price = float(product.get("price", 0) or 0)
    if max_price and max_price > 0:
        if price <= max_price:
            score += 10
        else:
            # 超预算按超出比例扣分，最多扣 30
            score -= min(30.0, (price - max_price) / max_price * 30)
    if min_price and min_price > 0:
        if price >= min_price:
            score += 5
        else:
            score -= min(20.0, (min_price - price) / min_price * 20)

    # 5) 关键词/属性重叠
    text = (str(product.get("name", "")) + " " + str(product.get("description", ""))).lower()
    q = (query or "").lower()
    if q:
        for kw in ATTRIBUTE_KEYWORDS:
            if kw in q and kw in text:
                score += 3
    if knowledge_tags:
        for t in knowledge_tags:
            if t and t.lower() in text:
                score += 2

    # 6) 历史反馈修正（冷启动为 0，不影响首次上线的排序）
    if feedback_weight:
        bonus = feedback_weight * FEEDBACK_K
        score += max(-FEEDBACK_CAP, min(FEEDBACK_CAP, bonus))

    return max(0.0, min(100.0, round(score, 1)))


def explain_score(
    query: str,
    product: dict,
    *,
    category: str = "",
    brand: str = "",
    gender: str = "",
    min_price: float = 0,
    max_price: float = 0,
    feedback_weight: float = 0.0,
) -> list[str]:
    """返回该商品得分的加分/扣分明细，用于日志排查和面试演示"可解释性"。

    不参与线上打分链路，score_product 才是唯一评分入口，
    这里只是把同一套规则的中间量翻译成人话。
    """
    items: list[str] = ["基础分 +55"]
    if category and product.get("category", "").strip().lower() == category.strip().lower():
        items.append(f"品类命中({category}) +15")
    if brand and product.get("brand", "").strip().lower() == brand.strip().lower():
        items.append(f"品牌命中({brand}) +10")
    price = float(product.get("price", 0) or 0)
    if max_price and max_price > 0:
        if price <= max_price:
            items.append(f"预算内({price}<={max_price}) +10")
        else:
            items.append(f"超预算({price}>{max_price}) -{min(30.0, (price - max_price) / max_price * 30):.1f}")
    if feedback_weight:
        b = max(-FEEDBACK_CAP, min(FEEDBACK_CAP, feedback_weight * FEEDBACK_K))
        items.append(f"历史反馈修正 {b:+.1f}")
    return items
