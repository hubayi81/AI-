import json

from langchain.tools import tool


def create_tools(products: list[dict]):
    """
    工厂函数：接收本次请求的商品列表，
    返回四个工具函数（商品数据通过闭包注入，不用全局变量）
    """

    # 内部筛选函数——只有 create_tools 内部的工具能调用
    def _filter(**kwargs):
        results = []
        for p in products:
            if kwargs.get("category") and p.get("category", "") != kwargs["category"]:
                continue
            if kwargs.get("brand") and p.get("brand", "").lower() != kwargs["brand"].lower():
                continue
            if kwargs.get("gender"):
                gender_map = {"男": "male", "女": "female", "通用": "unisex", "中性": "unisex"}
                filter_gender = gender_map.get(kwargs["gender"], kwargs["gender"])
                if p.get("gender", "") != filter_gender:
                    continue
            if kwargs.get("max_price") and kwargs["max_price"] > 0:
                if p.get("price", 0) > kwargs["max_price"]:
                    continue
            if kwargs.get("min_price") and kwargs["min_price"] > 0:
                if p.get("price", 0) < kwargs["min_price"]:
                    continue
            if kwargs.get("keyword"):
                kw = kwargs["keyword"].lower()
                desc = p.get("description", "").lower()
                name = p.get("name", "").lower()
                if kw not in desc and kw not in name:
                    continue
            results.append(p)
        return results[:8]

    @tool
    def search_products(keyword: str = "", category: str = "", brand: str = "",
                        gender: str = "", min_price: float = 0, max_price: float = 0) -> str:
        """在商品库中搜索鞋款。参数：
        keyword: 功能关键词，如缓震、透气、轻量、宽楦
        category: 鞋类，如跑鞋、运动鞋、篮球鞋、休闲鞋
        brand: 品牌名
        gender: 性别 male/female/unisex
        min_price: 最低预算
        max_price: 最高预算
        至少填一个条件。"""
        items = _filter(
            keyword=keyword, category=category, brand=brand,
            gender=gender, min_price=min_price, max_price=max_price
        )
        return json.dumps(items, ensure_ascii=False)

    @tool
    def analyze_outfit(top_wear: str = "", bottom_wear: str = "",
                       occasion: str = "", style: str = "") -> str:
        """根据用户穿搭描述匹配鞋款。参数：
        top_wear: 上装描述
        bottom_wear: 下装描述
        occasion: 场合（通勤/约会/逛街/运动）
        style: 风格偏好（简约/复古/街头/运动）"""
        style_to_category = {
            "简约": "休闲鞋",
            "复古": "板鞋",
            "街头": "运动鞋",
            "运动": "跑鞋",
            "户外": "户外鞋",
            "机能": "户外鞋",
            "登山": "登山鞋",
            "学院": "帆布鞋",
            "甜美": "帆布鞋",
            "潮流": "老爹鞋",
            "居家": "拖鞋",
            "清凉": "凉鞋",
        }

        occasion_to_keyword = {
            "通勤": "简约",
            "约会": "时尚",
            "逛街": "舒适",
            "运动": "透气",
            "跑步": "缓震",
            "登山": "防滑",
            "健身": "轻量",
            "日常": "百搭",
            "户外": "耐磨",
            "居家": "轻便",
            "夏天": "透气",
        }

        cat = style_to_category.get(style, "")
        kw = occasion_to_keyword.get(occasion, "")
        items = _filter(category=cat, keyword=kw)
        return json.dumps(items, ensure_ascii=False)

    @tool
    def compare_shoes(product_id_1: int, product_id_2: int) -> str:
        """对比两双鞋的优劣。参数：
        product_id_1: 第一双鞋的商品ID
        product_id_2: 第二双鞋的商品ID"""
        shoe1 = next((p for p in products if p.get("id") == product_id_1), None)
        shoe2 = next((p for p in products if p.get("id") == product_id_2), None)
        if not shoe1 or not shoe2:
            return json.dumps({"error": "未找到对应商品"})
        return json.dumps({"shoe_1": shoe1, "shoe_2": shoe2}, ensure_ascii=False)

    @tool
    def ask_clarify(question: str) -> str:
        """信息不够时生成追问问题。参数：
        question: 追问的具体问题"""
        return json.dumps({"question": question}, ensure_ascii=False)

    return [search_products, analyze_outfit, compare_shoes, ask_clarify]
