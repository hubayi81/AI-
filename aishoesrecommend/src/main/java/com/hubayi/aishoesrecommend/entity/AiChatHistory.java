package com.hubayi.aishoesrecommend.entity;

import java.time.LocalDateTime;

/**
 * AI 对话历史
 */
public class AiChatHistory {

    private Long id;
    private Long userId;
    private String conversationId;
    private String role;    // user 或 ai
    private String content;
    private LocalDateTime createTime;

    public AiChatHistory() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Long getUserId() { return userId; }
    public void setUserId(Long userId) { this.userId = userId; }

    public String getConversationId() { return conversationId; }
    public void setConversationId(String conversationId) { this.conversationId = conversationId; }

    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }

    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }

    public LocalDateTime getCreateTime() { return createTime; }
    public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }
}
