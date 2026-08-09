"""评测用固定商品目录（15 款，覆盖多品牌 / 多品类 / 多足型场景）。

单独成文件的原因：eval_engine.py 在模块顶层就构造了 ChatOpenAI 客户端，
从它 import 商品数据会连带拉起 langchain 和 API 配置，
离线评测脚本会因此变成"必须联网 + 必须有 API Key"才能跑。
数据和执行环境解耦，离线评测才真的离线。
"""

PRODUCTS = [
    {"id": 1, "name": "Air Zoom Pegasus 41", "brand": "Nike", "category": "跑鞋", "gender": "male", "price": 899, "description": "轻量缓震跑鞋，Zoom Air 气垫，适合日常训练和 5-10 公里路跑", "imageUrl": ""},
    {"id": 2, "name": "Ultraboost 5X", "brand": "Adidas", "category": "跑鞋", "gender": "unisex", "price": 1099, "description": "Boost 中底全掌缓震，Primeknit 飞织鞋面，脚感软弹适合日常通勤和恢复跑", "imageUrl": ""},
    {"id": 3, "name": "Gel-Kayano 30", "brand": "Asics", "category": "跑鞋", "gender": "male", "price": 1190, "description": "支撑稳定型跑鞋，DUOMAX 双密度中底，适合扁平足和过度内旋跑者", "imageUrl": ""},
    {"id": 4, "name": "Old Skool", "brand": "Vans", "category": "板鞋", "gender": "unisex", "price": 569, "description": "经典侧边条纹板鞋，耐磨硫化底，街头滑板风格", "imageUrl": ""},
    {"id": 5, "name": "Chuck Taylor All Star", "brand": "Converse", "category": "帆布鞋", "gender": "unisex", "price": 499, "description": "经典高帮帆布鞋，百搭单品，适合日常休闲", "imageUrl": ""},
    {"id": 6, "name": "Air Jordan 1 Low", "brand": "Nike", "category": "篮球鞋", "gender": "male", "price": 999, "description": "飞人经典低帮款，Air Sole 气垫，复古篮球鞋风格", "imageUrl": ""},
    {"id": 7, "name": "Cloudmonster 2", "brand": "On", "category": "跑鞋", "gender": "unisex", "price": 1299, "description": "CloudTec 镂空中底，极致缓震回弹，适合长距离路跑", "imageUrl": ""},
    {"id": 8, "name": "Classic Clog", "brand": "Crocs", "category": "休闲鞋", "gender": "unisex", "price": 399, "description": "轻便洞洞鞋，Croslite 材质，透气不闷脚，夏天必备", "imageUrl": ""},
    {"id": 9, "name": "Dunk Low", "brand": "Nike", "category": "运动鞋", "gender": "female", "price": 749, "description": "复古 Dunk 系列，配色清新百搭，适合日常通勤和逛街", "imageUrl": ""},
    {"id": 10, "name": "Gazelle Bold", "brand": "Adidas", "category": "休闲鞋", "gender": "female", "price": 799, "description": "厚底增高休闲鞋，翻毛皮鞋面，时尚复古风格", "imageUrl": ""},
    {"id": 11, "name": "Fresh Foam X 1080v13", "brand": "New Balance", "category": "跑鞋", "gender": "unisex", "price": 999, "description": "Fresh Foam X 顶级缓震中底，宽楦版本可选 2E/4E，适合宽脚跑者", "imageUrl": ""},
    {"id": 12, "name": "Adizero SL", "brand": "Adidas", "category": "竞速跑鞋", "gender": "male", "price": 699, "description": "Lightstrike Pro 中底，轻量竞速训练鞋，适合速度训练和比赛", "imageUrl": ""},
    {"id": 13, "name": "Gel-Nimbus 26", "brand": "Asics", "category": "跑鞋", "gender": "female", "price": 1290, "description": "PureGEL 顶级缓震，FF BLAST+ 中底，适合高足弓和需要软底的人群", "imageUrl": ""},
    {"id": 14, "name": "Speedcat OG", "brand": "Puma", "category": "板鞋", "gender": "unisex", "price": 699, "description": "复古赛车鞋薄底设计，翻毛皮+皮革拼接，适合窄脚瘦脚人群", "imageUrl": ""},
    {"id": 15, "name": "Go Walk 7", "brand": "Skechers", "category": "健步鞋", "gender": "unisex", "price": 599, "description": "Hyper Burst 超轻中底，一脚蹬设计，适合日常走路和久站", "imageUrl": ""},
]
