package com.hubayi.aishoesrecommend.client;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public class AiChatResponse {

    @JsonProperty("conversation_id")
    private String conversationId;

    private String reply;
    private String action;
    private List<RecommendResult> results;

    // AI 生成的追问建议（如"有更便宜的吗？"），前端渲染为可点击标签
    // 用户点一下就能继续对话，不需要自己打字
    private List<String> followUps;

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

    public List<String> getFollowUps() { return followUps; }
    public void setFollowUps(List<String> followUps) { this.followUps = followUps; }

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
