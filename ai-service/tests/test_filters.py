"""tools.apply_filters 纯函数单测（结构化过滤，抽到模块顶层后可测）。"""
from tools import apply_filters


PRODUCTS = [
    {"id": 1, "brand": "Nike", "category": "跑鞋", "gender": "male", "price": 899},
    {"id": 2, "brand": "Adidas", "category": "跑鞋", "gender": "unisex", "price": 1099},
    {"id": 3, "brand": "Vans", "category": "板鞋", "gender": "unisex", "price": 569},
    {"id": 4, "brand": "Nike", "category": "篮球鞋", "gender": "male", "price": 999},
    {"id": 5, "brand": "Adidas", "category": "休闲鞋", "gender": "female", "price": 799},
]


def test_no_filter_returns_all():
    assert len(apply_filters(PRODUCTS)) == 5


def test_category_filter():
    out = apply_filters(PRODUCTS, category="跑鞋")
    assert {p["id"] for p in out} == {1, 2}


def test_brand_english():
    out = apply_filters(PRODUCTS, brand="Nike")
    assert {p["id"] for p in out} == {1, 4}


def test_brand_chinese_maps_to_english():
    # "阿迪达斯" 应映射到 "adidas"
    out = apply_filters(PRODUCTS, brand="阿迪达斯")
    assert {p["id"] for p in out} == {2, 5}


def test_gender_chinese_map():
    out = apply_filters(PRODUCTS, gender="女")
    assert {p["id"] for p in out} == {5}


def test_max_price_filter():
    out = apply_filters(PRODUCTS, max_price=600)
    assert {p["id"] for p in out} == {3}


def test_min_price_filter():
    out = apply_filters(PRODUCTS, min_price=1000)
    # 仅 Adidas(1099) 价格 >= 1000
    assert {p["id"] for p in out} == {2}


def test_combined_filters():
    out = apply_filters(PRODUCTS, brand="Nike", category="跑鞋")
    assert {p["id"] for p in out} == {1}
