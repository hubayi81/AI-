import os
os.environ.pop("SSLKEYLOGFILE", None)  # 消除 Wireshark SSL 抓包的环境变量干扰

from fastapi import FastAPI
from schemas import ChatRequest, ChatResponse
from agent import process_message

app = FastAPI(title="AI 鞋类导购助手", version="3.0")


@app.get("/health")
def health():
    """健康检查"""
    return {"status": "ok"}


@app.post("/api/ai/agent/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Agent 对话入口"""
    # Pydantic 模型转 dict 列表（tools.py 里用的是 dict 操作）
    products = [p.model_dump() for p in req.products]

    result = process_message(
        conversation_id=req.conversation_id,
        user_message=req.message,
        products=products,
    )

    return ChatResponse(
        conversation_id=result["conversation_id"],
        reply=result["reply"],
        action=result["action"],
        results=result["results"],
    )


if __name__ == "__main__":
    import uvicorn
    print("AI Agent 服务启动：http://localhost:5000/docs")
    uvicorn.run(app, host="127.0.0.1", port=5000)