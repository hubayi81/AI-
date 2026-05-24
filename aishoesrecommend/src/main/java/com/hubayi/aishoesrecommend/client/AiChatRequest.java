package com.hubayi.aishoesrecommend.client;

import com.fasterxml.jackson.annotation.JsonProperty;

public class AiChatRequest {

    @JsonProperty("conversation_id")
    private String conversationId;

    private String message;

    public AiChatRequest() {}

    public AiChatRequest(String conversationId, String message) {
        this.conversationId = conversationId;
        this.message = message;
    }

    public String getConversationId() { return conversationId; }
    public void setConversationId(String conversationId) { this.conversationId = conversationId; }

    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }
}
