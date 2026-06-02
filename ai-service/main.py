import os
os.environ.pop("SSLKEYLOGFILE", None)  # 消除 Wireshark SSL 抓包的环境变量干扰

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from schemas import ChatRequest, ChatResponse
from agent import process_message, stream_agent

app = FastAPI(title="AI 鞋类导购助手", version="3.0")

# CORS 中间件 —— 允许前端跨域访问 SSE 流（浏览器同源策略要求）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """健康检查"""
    return {"status": "ok"}


@app.post("/api/ai/agent/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Agent 对话入口（非流式，保留兼容）"""
    products = [p.model_dump() for p in req.products]

    result = process_message(
        conversation_id=req.conversation_id,
        user_message=req.message,
        products=products,
        # 用户画像：Java 端传入，为空也无妨
        user_context=req.user_context,
    )

    return ChatResponse(
        conversation_id=result["conversation_id"],
        reply=result["reply"],
        action=result["action"],
        results=result["results"],
        # 追问建议：让用户点一下就能继续对话，降低输入门槛
        followUps=result.get("followUps"),
    )


@app.post("/api/ai/agent/chat/stream")
async def chat_stream(req: ChatRequest):
    """Agent 流式对话入口 —— 返回 SSE（Server-Sent Events）流"""
    products = [p.model_dump() for p in req.products]

    # StreamingResponse 配合异步生成器，每个 yield 立即推送到前端
    return StreamingResponse(
        stream_agent(
            conversation_id=req.conversation_id,
            user_message=req.message,
            products=products,
            # 用户画像用于个性化推荐
            user_context=req.user_context,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",      # 禁止浏览器缓存 SSE 流
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",        # 禁用 nginx 代理缓冲
        },
    )


if __name__ == "__main__":
    import uvicorn
    print("AI Agent 服务启动：http://localhost:5000/docs")
    uvicorn.run(app, host="127.0.0.1", port=5000)
