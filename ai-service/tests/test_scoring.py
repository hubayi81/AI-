"""scoring.score_product 纯函数单测（系统计算评分，不依赖 LLM）。"""
import math
import pytest

from scoring import score_product, FEEDBACK_CAP


def _p(**kw):
    base = {"id": 1, "name": "Test", "brand": "Nike", "category": "跑鞋",
            "gender": "male", "price": 900, "description": "缓震透气跑步"}
    base.update(kw)
    return base


def test_base_score_without_signals():
    # 无匹配信号 → 基础分 55（已夹在 0-100）
    s = score_product("随便聊聊", _p(), feedback_weight=0.0)
    assert s == 55.0


def test_category_and_brand_hit():
    s = score_product("Nike 跑鞋", _p(brand="Nike", category="跑鞋"),
                      brand="Nike", category="跑鞋", feedback_weight=0.0)
    # 55 + 15(品类) + 10(品牌) = 80
    assert s == 80.0


def test_price_over_budget_penalty():
    # 超预算按超出比例扣分，最多 30
    s_over = score_product("鞋", _p(price=1500),
                           max_price=1000, feedback_weight=0.0)
    assert s_over == pytest.approx(55 - 15.0)  # 500/1000*30 = 15


def test_price_under_budget_no_penalty():
    s = score_product("鞋", _p(price=800),
                      max_price=1000, feedback_weight=0.0)
    assert s == 65.0  # 55 + 10 预算内


def test_gender_match():
    s = score_product("男鞋", _p(gender="male"), gender="男", feedback_weight=0.0)
    assert s == 60.0  # 55 + 5


def test_attribute_overlap_bonus():
    # query 与 description 同时含"缓震" → +3
    s = score_product("缓震好", _p(description="轻量缓震跑鞋"),
                      feedback_weight=0.0)
    assert s == 58.0


def test_feedback_weight_zero_when_cold_start():
    # 无反馈（weight=0）→ 与纯内容分一致
    a = score_product("Nike 跑鞋", _p(brand="Nike", category="跑鞋"),
                       brand="Nike", category="跑鞋", feedback_weight=0.0)
    b = score_product("Nike 跑鞋", _p(brand="Nike", category="跑鞋"),
                       brand="Nike", category="跑鞋", feedback_weight=0.0)
    assert a == b


def test_feedback_weight_capped():
    # 极大的正向权重被封顶到 FEEDBACK_CAP（8）
    s = score_product("鞋", _p(), feedback_weight=10.0)
    # 55 + min(8, 10*20=200→cap 8) = 63
    assert s == 55.0 + FEEDBACK_CAP


def test_score_clamped_to_100():
    s = score_product("Nike 跑鞋缓震透气", _p(brand="Nike", category="跑鞋",
                                            description="缓震透气跑步训练"),
                      brand="Nike", category="跑鞋",
                      feedback_weight=5.0)
    assert 0.0 <= s <= 100.0


def test_score_is_deterministic():
    args = dict(query="Nike 跑鞋", product=_p(brand="Nike", category="跑鞋"),
                brand="Nike", category="跑鞋", feedback_weight=0.1)
    assert score_product(**args) == score_product(**args)
