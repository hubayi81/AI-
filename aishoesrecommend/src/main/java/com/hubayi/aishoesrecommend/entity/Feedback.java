package com.hubayi.aishoesrecommend.entity;

import java.time.LocalDateTime;

/**
 * AI 推荐反馈。
 * 用户对 AI 的每条回复可以点 👍 或 👎，
 * 积累反馈数据用于后续评估推荐质量、优化 prompt。
 */
public class Feedback {

    private Long id;
    private Long userId;
    private String conversationId;
    // 用户当时的提问
    private String userMessage;
    // AI 的完整回复
    private String aiReply;
    // "like" 或 "dislike"
    private String feedback;
    private LocalDateTime createTime;

    public Feedback() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Long getUserId() { return userId; }
    public void setUserId(Long userId) { this.userId = userId; }

    public String getConversationId() { return conversationId; }
    public void setConversationId(String conversationId) { this.conversationId = conversationId; }

    public String getUserMessage() { return userMessage; }
    public void setUserMessage(String userMessage) { this.userMessage = userMessage; }

    public String getAiReply() { return aiReply; }
    public void setAiReply(String aiReply) { this.aiReply = aiReply; }

    public String getFeedback() { return feedback; }
    public void setFeedback(String feedback) { this.feedback = feedback; }

    public LocalDateTime getCreateTime() { return createTime; }
    public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }
}
