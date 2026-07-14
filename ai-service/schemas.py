#定义数据结构
#Pydantic 模型，定义了接口的输入输出长什么样
# Product: 商品有哪些字段（id/name/price/category...）

from pydantic import BaseModel

class Product(BaseModel):
    """一个商品"""
    id:int
    name:str
    brand:str
    category:str
    gender:str = ""          # male / female / unisex
    price:float
    imageUrl:str = ""        # 商品图片 URL
    description:str = ""
    color:str = ""
    sizeRange:str = ""
    stock:int = 0

class ChatRequest(BaseModel):
    """前端发来的请求"""
    conversation_id:str | None = None
    message:str
    products:list[Product] = []
    # 用户画像上下文（Java 端根据收藏/历史计算后传入，可为空）
    user_context:str = ""
    # 对话历史：Java 端从 MySQL 查出后传入，Python 用于恢复 Agent 记忆
    # 为什么由 Java 传入而不是 Python 自己查？—— Python 不连数据库，保持架构简单
    history:list[dict] = []

class RecommendResult(BaseModel):
    """推荐结果里的每一项"""
    productId:int
    name:str
    score:int
    reason:str

class ChatResponse(BaseModel):
    """返回给前端的响应（非流式）"""
    conversation_id:str
    reply:str
    action:str = "chat"
    results:list[RecommendResult] | None = None
    # 追问建议：AI 生成的后续问题，前端渲染为可点击标签
    followUps:list[str] | None = None
