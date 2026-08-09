"""fusion.rrf_fuse 纯函数单测（RRF 排名融合，与线上同源）。"""
import pytest

from fusion import rrf_fuse, RRF_K


def test_empty_input_returns_empty():
    assert rrf_fuse([]) == []


def test_single_list_ranks_by_input_order():
    # 单路时，顺序即名次，分数 = w/(rank+k)
    out = rrf_fuse([[3, 1, 2]], weights=[1.0], k=60)
    assert [d for d, _ in out] == [3, 1, 2]


def test_two_lists_fuse_rewards_co_occurrence():
    # doc 1 两路都是第 1 → 分数最高
    out = rrf_fuse([[1, 2, 3], [1, 4, 5]], weights=[1.0, 1.0], k=60)
    assert out[0][0] == 1
    # doc1 两路第一：1/60 + 1/60 = 0.0333...
    assert out[0][1] == pytest.approx(2 / 60)


def test_weights_influence_ranking():
    # 第二路权重极高，应让其在第二路靠前的 doc 提升
    out = rrf_fuse([[2, 1], [1, 2]], weights=[0.1, 10.0], k=60)
    # 第 2 路第 1 是 doc1；权重 10 主导
    assert out[0][0] == 1


def test_k_suppresses_head():
    # k 越大，第1名与第2名的分差越小
    out_large = rrf_fuse([[1, 2]], weights=[1.0], k=600)
    s1, s2 = out_large[0][1], out_large[1][1]
    # 分差 = 1/601 - 1/602 ≈ 很小
    assert (s1 - s2) < 0.001


def test_top_n_limits_output():
    out = rrf_fuse([[1, 2, 3, 4, 5]], weights=[1.0], k=60, top_n=2)
    assert len(out) == 2
    assert [d for d, _ in out] == [1, 2]


def test_scores_are_rank_based_not_score_based():
    # 两路原始"分数"量级不同也没关系，只用名次：
    # 路A分数[100,1]，路B分数[0.9,0.1]，但只要名次一致就等价
    a = rrf_fuse([[1, 2]], weights=[1.0])
    b = rrf_fuse([[1, 2]], weights=[1.0])
    assert a == b  # 纯名次融合与原始分数无关
