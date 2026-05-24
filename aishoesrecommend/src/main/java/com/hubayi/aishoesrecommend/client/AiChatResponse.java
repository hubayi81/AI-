package com.hubayi.aishoesrecommend.client;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public class AiChatResponse {

    @JsonProperty("conversation_id")
    private String conversationId;

    private String reply;
    private String action;
    private List<RecommendResult> results;

    public AiChatResponse() {}

    // ---- getter / setter ----
    public String getConversationId() { return conversationId; }
    public void setConversationId(String conversationId) { this.conversationId = conversationId; }

    public String getReply() { return reply; }
    public void setReply(String reply) { this.reply = reply; }

    public String getAction() { return action; }
    public void setAction(String action) { this.action = action; }

    public List<RecommendResult> getResults() { return results; }
    public void setResults(List<RecommendResult> results) { this.results = results; }

    // ---- 内部类：推荐结果 ----
    public static class RecommendResult {
        private int productId;
        private String name;
        private int score;
        private String reason;

        public RecommendResult() {}

        public int getProductId() { return productId; }
        public void setProductId(int productId) { this.productId = productId; }

        public String getName() { return name; }
        public void setName(String name) { this.name = name; }

        public int getScore() { return score; }
        public void setScore(int score) { this.score = score; }

        public String getReason() { return reason; }
        public void setReason(String reason) { this.reason = reason; }
    }
}
