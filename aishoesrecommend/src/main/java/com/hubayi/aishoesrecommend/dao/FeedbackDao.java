package com.hubayi.aishoesrecommend.dao;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.Map;

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

    /**
     * 统计用户 👍/👎 数量。即使没有反馈记录也返回 likes=0, dislikes=0。
     * 为什么不用 queryForMap？—— 用户没有反馈时查不出任何行，queryForMap 会抛异常。
     * 用 queryForList 兜底更安全。
     */
    public Map<String, Object> countByUserId(Long userId) {
        String sql = """
            SELECT
                COUNT(CASE WHEN feedback = 'like' THEN 1 END) AS likes,
                COUNT(CASE WHEN feedback = 'dislike' THEN 1 END) AS dislikes
            FROM ai_feedback WHERE user_id = ?
            """;
        var rows = jdbc.queryForList(sql, userId);
        if (!rows.isEmpty()) return rows.get(0);
        return Map.of("likes", 0L, "dislikes", 0L);
    }
}
