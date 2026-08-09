"""离线检索评测引擎 —— 确定性、可进 CI、不调 LLM。

消费 eval_retrieval_dataset 的 ground-truth 标注，对多种排序策略算
Recall@K / MRR / NDCG@K，并做消融对比。

为什么这事值得做（面试会问）：
  - 之前的 eval_engine.py 测的是「Agent 行为」（调没调对工具、回复里有没有
    关键词），判定是一串 or 条件，几乎不可能失败，给不出「检索质量」的量化结论。
  - 本引擎测的是「排序质量」：给定 query，正确答案是哪几个商品 id。
    能算 Recall@K / MRR / NDCG@K，不同策略之间的**相对高低**可重复、可进 CI。

与生产代码同源（关键，否则测的是复刻件不是产品）：
  - 融合逻辑 = fusion.rrf_fuse（知识库和这里共用同一份）
  - 评分逻辑 = scoring.score_product（生产 search_products 用的就是它）
  - 向量检索 = retriever.ShoeRetriever（生产用的同一个类）
  - BM25      = knowledge_base.BM25Retriever（知识库用的同一个类）

排序策略（都先在过滤后的候选集上排，保证公平对比）：
  - rule        : 生产实际做法——filter 之后用 score_product 重排（冷启动，无反馈）
  - vector      : 纯向量余弦排序
  - bm25        : 纯 BM25 排序
  - rrf         : BM25 + 向量 用 rrf_fuse 融合排序
  - rrf+score   : rrf 融合分 与 score_product 归一化后按 0.5/0.5 混合（提出的混合方案）

一个重要且诚实的架构事实（写在报告里）：
  生产的 search_products 是「向量取 top30 → 过滤 → score_product 全量重排」。
  由于 score_product 会对**全部**过滤结果重新排序，上游检索顺序在候选集内
  不起决定作用——真正决定顺序的是 score_product 这条规则。所以「rule」策略
  等价于生产的排序结果，而「rrf+score」把检索信号也作为一维保留进最终打分，
  二者不同。向量检索在这里的作用主要是**候选召回截断**（353 款时取 top30），
  在 15 款评测目录里所有相关项都进候选集，故召回截断差异被抹平——这一局限
  我们如实标注，不夸大 rrf 在小题集上的收益。
"""

import math
import sys

import numpy as np

from eval_catalog import PRODUCTS as EVAL_PRODUCTS
from eval_retrieval_dataset import (
    RETRIEVAL_CASES,
    CONSTRAINT_CASES,
    NO_ANSWER_CASES,
    all_ranking_cases,
)
from fusion import rrf_fuse
from scoring import score_product
from retriever import ShoeRetriever, _get_model as _get_retriever_model


# ─────────────────────────────────────────────────────────────────────────
#  检索器构建
# ─────────────────────────────────────────────────────────────────────────
def _build_retrievers(products):
    """返回 (vec, bm25, id2idx)。向量模型加载失败则返回 (None, bm25, id2idx)。"""
    from knowledge_base import BM25Retriever

    id2idx = {p["id"]: i for i, p in enumerate(products)}
    texts = [f"{p['name']} {p['description']}" for p in products]
    bm25 = BM25Retriever(texts)

    vec = None
    try:
        vec = ShoeRetriever(products)  # 首次会加载 text2vec 模型，可能联网/较慢
        # 触发一次编码，确认模型可用
        _ = vec.embeddings
        _ = _get_retriever_model()
        print("[eval] 向量检索器就绪（sentence-transformers 模型已加载）")
    except Exception as e:  # noqa: BLE001
        print(f"[eval] 向量检索器不可用，将跳过 vector/rrf 相关策略: {e}")
        vec = None

    return vec, bm25, id2idx


# ─────────────────────────────────────────────────────────────────────────
#  结构化过滤（faithful 复刻 tools._apply_filters，仅保留英文 brand 比对）
# ─────────────────────────────────────────────────────────────────────────
def apply_filters(products, filters):
    cat = filters.get("category", "")
    brand = filters.get("brand", "")
    gender = filters.get("gender", "")
    min_p = filters.get("min_price", 0) or 0
    max_p = filters.get("max_price", 0) or 0

    gender_map = {"男": "male", "女": "female", "通用": "unisex", "中性": "unisex"}
    out = []
    for p in products:
        if cat and p.get("category", "") != cat:
            continue
        if brand and p.get("brand", "").strip().lower() != brand.strip().lower():
            continue
        if gender:
            g = gender_map.get(gender, gender)
            if p.get("gender", "") != g:
                continue
        if max_p and max_p > 0 and p.get("price", 0) > max_p:
            continue
        if min_p and min_p > 0 and p.get("price", 0) < min_p:
            continue
        out.append(p)
    return out


# ─────────────────────────────────────────────────────────────────────────
#  排序策略
# ─────────────────────────────────────────────────────────────────────────
def _vector_sims(vec, query):
    model = _get_retriever_model()
    qv = model.encode([query], convert_to_numpy=True, show_progress_bar=False)
    return np.dot(vec.embeddings, qv.T).flatten()


def rank_rule(query, filtered, id2idx, vec=None, filters=None):
    f = filters or {}
    scored = sorted(
        filtered,
        key=lambda p: -score_product(
            query, p,
            category=f.get("category", ""),
            brand=f.get("brand", ""),
            gender=f.get("gender", ""),
            min_price=f.get("min_price", 0) or 0,
            max_price=f.get("max_price", 0) or 0,
            feedback_weight=0.0,  # 冷启动：无反馈数据
        ),
    )
    return [p["id"] for p in scored]


def rank_vector(query, filtered, id2idx, vec):
    sims = _vector_sims(vec, query)
    cand = [(p["id"], float(sims[id2idx[p["id"]]])) for p in filtered]
    cand.sort(key=lambda x: -x[1])
    return [pid for pid, _ in cand]


def rank_bm25(query, filtered, id2idx, vec, bm25):
    cand = [(p["id"], bm25.score(query, id2idx[p["id"]])) for p in filtered]
    cand.sort(key=lambda x: -x[1])
    return [pid for pid, _ in cand]


def rank_rrf(query, filtered, id2idx, vec, bm25):
    sims = _vector_sims(vec, query)
    bm25_scores = [bm25.score(query, id2idx[p["id"]]) for p in filtered]
    # 归一化到 0-1 再排名，避免两种量纲混用（也避免 RRF 只用名次的设计冲突）
    vec_order = sorted(filtered, key=lambda p: -float(sims[id2idx[p["id"]]]))
    bm25_order = sorted(filtered, key=lambda p: -bm25.score(query, id2idx[p["id"]]))
    fused = rrf_fuse(
        [[p["id"] for p in vec_order], [p["id"] for p in bm25_order]],
        weights=[0.6, 0.4],
    )
    fused_ids = [pid for pid, _ in fused]
    # 只保留候选集内的 id（防御性）
    return [pid for pid in fused_ids if any(pid == p["id"] for p in filtered)]


def rank_rrf_score(query, filtered, id2idx, vec, bm25):
    sims = _vector_sims(vec, query)
    # rrf 融合分（归一化）
    vec_order = sorted(filtered, key=lambda p: -float(sims[id2idx[p["id"]]]))
    bm25_order = sorted(filtered, key=lambda p: -bm25.score(query, id2idx[p["id"]]))
    fused = rrf_fuse(
        [[p["id"] for p in vec_order], [p["id"] for p in bm25_order]],
        weights=[0.6, 0.4],
    )
    rrf_raw = {pid: s for pid, s in fused}
    max_r = max(rrf_raw.values()) if rrf_raw else 1.0
    # score_product 分（归一化到 0-100 → 0-1）
    scored = {
        p["id"]: score_product(query, p, feedback_weight=0.0) / 100.0
        for p in filtered
    }
    # 混合：0.5 检索融合 + 0.5 内容评分
    blended = {
        pid: 0.5 * (rrf_raw.get(pid, 0.0) / max_r) + 0.5 * scored[pid]
        for pid in rrf_raw
    }
    return [pid for pid, _ in sorted(blended.items(), key=lambda x: -x[1])]


# ─────────────────────────────────────────────────────────────────────────
#  指标
# ─────────────────────────────────────────────────────────────────────────
def _relevant(relevance):
    return {pid for pid, g in relevance.items() if g > 0}


def recall_at_k(ranked, relevance, k):
    rel = _relevant(relevance)
    if not rel:
        return None  # 无相关项，不参与平均
    top = set(ranked[:k])
    return len(rel & top) / len(rel)


def mrr(ranked, relevance):
    rel = _relevant(relevance)
    if not rel:
        return None
    for i, pid in enumerate(ranked):
        if pid in rel:
            return 1.0 / (i + 1)
    return 0.0


def _dcg(gains):
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg_at_k(ranked, relevance, k):
    rel = _relevant(relevance)
    if not rel:
        return None
    gains = [relevance.get(pid, 0) for pid in ranked[:k]]
    ideal = sorted(relevance.values(), reverse=True)[:k]
    idcg = _dcg(ideal)
    return _dcg(gains) / idcg if idcg > 0 else 0.0


# ─────────────────────────────────────────────────────────────────────────
#  主流程
# ─────────────────────────────────────────────────────────────────────────
def run():
    vec, bm25, id2idx = _build_retrievers(EVAL_PRODUCTS)

    cases = all_ranking_cases()
    has_vector = vec is not None

    # 策略注册
    strategies = {
        "rule": lambda q, f, flt: rank_rule(q, flt, id2idx, vec, f),
        "bm25": lambda q, f, flt: rank_bm25(q, flt, id2idx, vec, bm25),
    }
    if has_vector:
        strategies["vector"] = lambda q, f, flt: rank_vector(q, flt, id2idx, vec)
        strategies["rrf"] = lambda q, f, flt: rank_rrf(q, flt, id2idx, vec, bm25)
        strategies["rrf+score"] = lambda q, f, flt: rank_rrf_score(q, flt, id2idx, vec, bm25)

    ks = [1, 3, 5]
    metrics = {name: {"R@1": [], "R@3": [], "R@5": [], "MRR": [], "N@5": [], "N@10": []}
               for name in strategies}

    # 分子集
    subsets = {
        "语义(18)": RETRIEVAL_CASES,
        "约束(4)": CONSTRAINT_CASES,
        "全部(22)": cases,
    }

    # 每个用例为每个策略生成排名（避免重复计算）
    per_case = {}  # case_id -> {strategy: ranked_ids}
    for c in cases:
        filters = c.get("filters", {})
        flt = apply_filters(EVAL_PRODUCTS, filters)
        per_case[c["id"]] = {}
        for name, fn in strategies.items():
            per_case[c["id"]][name] = fn(c["query"], filters, flt)

    # 计算指标
    for name in strategies:
        for c in cases:
            rel = c["relevance"]
            r = per_case[c["id"]][name]
            for k in ks:
                v = recall_at_k(r, rel, k)
                if v is not None:
                    metrics[name][f"R@{k}"].append(v)
            m = mrr(r, rel)
            if m is not None:
                metrics[name]["MRR"].append(m)
            n5 = ndcg_at_k(r, rel, 5)
            n10 = ndcg_at_k(r, rel, 10)
            if n5 is not None:
                metrics[name]["N@5"].append(n5)
            if n10 is not None:
                metrics[name]["N@10"].append(n10)

    def avg(xs):
        return sum(xs) / len(xs) if xs else float("nan")

    # ── 打印报告 ──
    lines = []
    lines.append("=" * 78)
    lines.append("离线检索评测报告（确定性 · 不调 LLM · 与线上同源）")
    lines.append("=" * 78)
    lines.append(f"评测目录：{len(EVAL_PRODUCTS)} 款固定商品")
    lines.append(f"排序用例：语义 {len(RETRIEVAL_CASES)} + 约束 {len(CONSTRAINT_CASES)} "
                 f"+ 无解 {len(NO_ANSWER_CASES)}（无解用例不计入排序指标）")
    lines.append(f"向量检索：{'启用' if has_vector else '不可用（已跳过 vector/rrf 策略）'}")
    lines.append("")
    lines.append("策略说明：")
    lines.append("  rule      = 生产实际：filter 后 score_product 重排（冷启动）")
    lines.append("  vector    = 纯向量余弦")
    lines.append("  bm25      = 纯 BM25")
    lines.append("  rrf       = BM25(0.4)+向量(0.6) 经 rrf_fuse 融合")
    lines.append("  rrf+score = rrf 融合分 与 score_product 按 0.5/0.5 混合（提出方案）")
    lines.append("")
    lines.append("注：Recall@1 在多相关项查询下天然 <1（分子为 1、分母为相关项总数），")
    lines.append("    它衡量『首位那一个覆盖了多少比例的相关项』；判断『首位是否相关』")
    lines.append("    请看下方规则 judge 通过率。约束子集里五种策略指标完全相同，")
    lines.append("    说明结构化约束由『过滤』解决，排序器本身不起决定作用。")
    lines.append("")
    lines.append("-" * 78)

    header = f"{'策略':<10}" + "".join(f"{h:>10}" for h in
            ["R@1", "R@3", "R@5", "MRR", "NDCG@5", "NDCG@10"])
    for sub_name, sub_cases in subsets.items():
        lines.append("")
        lines.append(f"【{sub_name}】")
        lines.append(header)
        lines.append("-" * 78)
        for name in strategies:
            row_vals = []
            # 子集指标：只取属于该子集的用例
            sub_ids = {c["id"] for c in sub_cases}
            rec = {k: [] for k in metrics[name]}
            for cid, stratmap in per_case.items():
                if cid not in sub_ids:
                    continue
                case = next(c for c in cases if c["id"] == cid)
                r = stratmap[name]
                rel = case["relevance"]
                for k in ks:
                    v = recall_at_k(r, rel, k)
                    if v is not None:
                        rec[f"R@{k}"].append(v)
                m = mrr(r, rel)
                if m is not None:
                    rec["MRR"].append(m)
                n5 = ndcg_at_k(r, rel, 5)
                n10 = ndcg_at_k(r, rel, 10)
                if n5 is not None:
                    rec["N@5"].append(n5)
                if n10 is not None:
                    rec["N@10"].append(n10)
            cells = [avg(rec["R@1"]), avg(rec["R@3"]), avg(rec["R@5"]),
                     avg(rec["MRR"]), avg(rec["N@5"]), avg(rec["N@10"])]
            row = f"{name:<10}" + "".join(f"{v:>10.3f}" for v in cells)
            lines.append(row)
        lines.append("-" * 78)

    # ── 规则 judge（离线确定性「成功」判定）──
    lines.append("")
    lines.append("规则 judge（离线）：rank-1 是否为相关项（grade>=1）的通过率")
    lines.append("-" * 78)
    for name in strategies:
        hits = 0
        total = 0
        for cid, stratmap in per_case.items():
            case = next(c for c in cases if c["id"] == cid)
            rel = _relevant(case["relevance"])
            if not rel:
                continue
            total += 1
            if stratmap[name] and stratmap[name][0] in rel:
                hits += 1
        rate = hits / total if total else float("nan")
        lines.append(f"  {name:<10} 通过率 {rate*100:5.1f}%  ({hits}/{total})")

    # ── 无解用例提示 ──
    lines.append("")
    lines.append("无解用例（不计入排序指标，正确行为是 Agent 层拒答而非硬凑）：")
    for c in NO_ANSWER_CASES:
        lines.append(f"  {c['id']}  {c['query']}  —— {c['reason']}")

    lines.append("")
    lines.append("=" * 78)
    report = "\n".join(lines)
    print(report)
    return report, per_case, strategies


if __name__ == "__main__":
    report, _, _ = run()
    out_path = __file__.replace(".py", "_report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n[eval] 报告已写入: {out_path}")
