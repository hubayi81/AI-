package com.hubayi.aishoesrecommend.client;

import com.fasterxml.jackson.annotation.JsonProperty;

public class AiChatRequest {

    @JsonProperty("conversation_id")
    private String conversationId;

    private String message;

    // 用户画像上下文：由 Java 端根据收藏和历史生成后传给 Python
    // 让 AI 了解用户偏好（喜欢什么品牌/品类/价位），推荐更精准
    @JsonProperty("user_context")
    private String userContext;

    public AiChatRequest() {}

    public AiChatRequest(String conversationId, String message) {
        this.conversationId = conversationId;
        this.message = message;
    }

    public String getConversationId() { return conversationId; }
    public void setConversationId(String conversationId) { this.conversationId = conversationId; }

    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }

    public String getUserContext() { return userContext; }
    public void setUserContext(String userContext) { this.userContext = userContext; }
}
