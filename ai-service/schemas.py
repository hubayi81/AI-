from pydantic import BaseModel

class Product(BaseModel):
    """一个商品"""
    id:int
    name:str
    brand:str
    category:str
    price:float
    description:str = ""
    color:str = ""
    sizeRange:str = ""
    stock:int = 0

class ChatRequest(BaseModel):
    """前端发来的请求"""
    conversation_id:str | None = None
    message:str
    products:list[Product] = []

class RecommendResult(BaseModel):
    """推荐结果里的每一项"""
    productId:int
    name:str
    score:int
    reason:str

class ChatResponse(BaseModel):
    """返回给前端的响应"""
    conversation_id:str
    reply:str
    action:str = "chat"
    results:list[RecommendResult] | None = None
