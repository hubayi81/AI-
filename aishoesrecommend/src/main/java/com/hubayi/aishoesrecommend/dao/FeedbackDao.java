package com.hubayi.aishoesrecommend.dao;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class FeedbackDao {

    private final JdbcTemplate jdbc;

    public FeedbackDao(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /**
     * 保存反馈。
     * 先用 DELETE 清理同会话旧反馈再用 INSERT ——
     * 因为用户可能在同一条回复上先点 👍 再改点 👎，这里用"覆盖"策略避免重复行。
     */
    public int save(Long userId, String conversationId,
                    String userMessage, String aiReply, String feedback) {
        // 如果该会话已有反馈，先删
        String delSql = "DELETE FROM ai_feedback WHERE user_id = ? AND conversation_id = ?";
        jdbc.update(delSql, userId, conversationId);
        // 再插入新反馈
        String sql = "INSERT INTO ai_feedback(user_id, conversation_id, user_message, ai_reply, feedback) VALUES (?,?,?,?,?)";
        return jdbc.update(sql, userId, conversationId, userMessage, aiReply, feedback);
    }
}
