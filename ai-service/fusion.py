"""Reciprocal Rank Fusion（RRF）——多路召回结果的排名融合。

抽成独立模块的原因：知识库检索和商品检索都要用同一套融合逻辑，
更重要的是**评测脚本必须跑线上同一份代码**。
如果评测里复刻一份 RRF，那测的是复刻件不是产品，指标再好看也没意义。

公式：score(d) = Σ_i  w_i / (rank_i(d) + k)

为什么用 RRF 而不是把两路的原始分数加权相加？
  —— 向量余弦相似度在 [-1,1]、BM25 分数无上界，两者量纲完全不同，
     直接加权相加等于让 BM25 单方面主导。RRF 只用**名次**不用分数，
     天然免疫量纲问题，这也是它在多路召回里成为默认选择的原因。

为什么 k = 60？
  —— 出自 Cormack et al. 2009 的原始论文经验值。k 的作用是压制头部：
     k 越大，第 1 名和第 10 名的分差越小、越依赖"被多路同时召回"这个信号；
     k 越小越信任单路的头部结果。60 在候选集只有几十到几百时是稳妥值。
     注意 RRF 分数天然极小（k=60 时单路贡献约 1/60 ≈ 0.0167），
     任何要跟固定阈值比较的地方都必须先归一化——这是踩过的坑。
"""

RRF_K = 60


def rrf_fuse(ranked_lists: list[list[int]],
             weights: list[float] | None = None,
             k: int = RRF_K,
             top_n: int | None = None) -> list[tuple[int, float]]:
    """融合多路召回结果。

    Args:
        ranked_lists: 每一路的文档 id 列表，按相关度从高到低排列
        weights:      每一路的权重，缺省全 1.0
        k:            RRF 平滑常数
        top_n:        只返回前 n 条，None 表示全返回

    Returns:
        [(doc_id, rrf_score), ...] 按分数降序
    """
    if not ranked_lists:
        return []
    if weights is None:
        weights = [1.0] * len(ranked_lists)

    scores: dict[int, float] = {}
    for lst, w in zip(ranked_lists, weights):
        for rank, doc_id in enumerate(lst):
            scores[doc_id] = scores.get(doc_id, 0.0) + w / (rank + k)

    merged = sorted(scores.items(), key=lambda x: -x[1])
    return merged[:top_n] if top_n else merged
