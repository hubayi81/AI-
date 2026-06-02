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
