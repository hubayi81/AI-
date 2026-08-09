"""db._compute_weights 纯函数单测（贝叶斯平滑 / m-estimate 反馈权重）。

关键性质：冷启动（n=0）权重为 0，评分自动退化为纯内容分；
小样本不偏离全局均值（抗噪），赞/踩对称生效。
"""
import pytest

from db import _compute_weights, _FEEDBACK_ALPHA


def test_no_feedback_returns_empty():
    # 完全没有反馈 → 全局 total=0 → 返回 {}（冷启动）
    assert _compute_weights([]) == {}


def test_cold_start_single_product_zero_weight():
    # 某商品 0 赞 0 踩（n=0）→ 无全局均值可供比较，权重 0
    rows = [{"product_id": 1, "likes": 0, "dislikes": 0}]
    # total=0 → 直接返回 {}（与“无反馈”同义）
    assert _compute_weights(rows) == {}


def test_balanced_feedback_zero_weight():
    # 两商品各 5 赞 5 踩 → mu=0.5，各自 p_hat=0.5 → w=0
    rows = [
        {"product_id": 1, "likes": 5, "dislikes": 5},
        {"product_id": 2, "likes": 5, "dislikes": 5},
    ]
    w = _compute_weights(rows)
    assert w["1"] == 0.0 and w["2"] == 0.0


def test_liked_product_gets_positive_weight():
    # A: 10赞0踩, B: 0赞10踩, mu=0.5
    rows = [
        {"product_id": 1, "likes": 10, "dislikes": 0},
        {"product_id": 2, "likes": 0, "dislikes": 10},
    ]
    w = _compute_weights(rows)
    # A: p_hat=(10+10*0.5)/(10+10)=0.75 → w=+0.25
    assert w["1"] == pytest.approx(0.25)
    # B: p_hat=(0+10*0.5)/(10+10)=0.25 → w=-0.25（对称：纯踩得负向）
    assert w["2"] == pytest.approx(-0.25)


def test_small_sample_pulled_toward_mean():
    # 只有 1 赞 0 踩 一个商品：mu=1.0，p_hat=(1+alpha*1)/(1+alpha)=1 → w=0
    # 说明即使单样本 100% 好评，也不会被当成"绝对完美"顶到极端。
    rows = [{"product_id": 1, "likes": 1, "dislikes": 0}]
    w = _compute_weights(rows)
    assert w["1"] == pytest.approx(0.0)


def test_negative_weight_for_disliked():
    # 非对称样本：商品1 差评为主，商品2 中性
    rows = [
        {"product_id": 1, "likes": 1, "dislikes": 9},   # 差评为主
        {"product_id": 2, "likes": 5, "dislikes": 5},   # 中性
    ]
    w = _compute_weights(rows)
    # total_like=6, total_dis=14, mu=0.3
    # 商品1: p_hat=(1+10*0.3)/(10+10)=4/20=0.2 → w=0.2-0.3=-0.1（负向）
    assert w["1"] == pytest.approx(-0.1)
    assert w["1"] < 0
    # 商品2 中性(raw 0.5)，但全局 mu=0.3（差评偏多），
    # 故相对全局均值略偏高 → 小正权重 +0.1（平滑后仍被拉回，不极端）
    assert w["2"] == pytest.approx(0.1)
