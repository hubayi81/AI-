import os

os.environ.pop("SSLKEYLOGFILE", None)
import requests
import json

products = [
    {"id": 1, "name": "Air Zoom Pegasus", "brand": "Nike",
     "category": "跑鞋", "gender": "male", "price": 399,
     "description": "轻量缓震跑鞋，适合日常训练",
     "color": "黑色", "sizeRange": "39-44", "stock": 10},
    {"id": 2, "name": "Ultraboost", "brand": "Adidas",
     "category": "跑鞋", "gender": "unisex", "price": 450,
     "description": "全掌缓震，脚感柔软，宽楦设计",
     "color": "白色", "sizeRange": "38-45", "stock": 8},
    {"id": 3, "name": "Gel-Kayano", "brand": "Asics",
     "category": "跑鞋", "gender": "male", "price": 380,
     "description": "支撑稳定型跑鞋，适合扁平足",
     "color": "蓝色", "sizeRange": "39-44", "stock": 5}
]

r = requests.post(
    "http://localhost:5000/api/ai/agent/chat",
    json={"message": "男生脚宽跑步5公里预算450", "products": products}
)
data = r.json()
print("=== reply ===")
print(data["reply"])
print()
print("action:", data["action"])
print("results:", json.dumps(data["results"], ensure_ascii=False))
