package com.hubayi.aishoesrecommend.dao;

import com.hubayi.aishoesrecommend.entity.AiChatHistory;
import org.springframework.jdbc.core.BeanPropertyRowMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Map;

@Repository
public class AiChatHistoryDao {

    private final JdbcTemplate jdbc;

    public AiChatHistoryDao(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** 保存一条消息 */
    public int insert(Long userId, String conversationId, String role, String content) {
        String sql = "INSERT INTO ai_chat_history(user_id, conversation_id, role, content) VALUES (?, ?, ?, ?)";
        return jdbc.update(sql, userId, conversationId, role, content);
    }

    /** 查用户最近 N 条历史（按时间倒序），用于个人中心列表 */
    public List<AiChatHistory> findByUserId(Long userId, int limit) {
        String sql = "SELECT id, user_id, conversation_id, role, content, create_time FROM ai_chat_history WHERE user_id = ? ORDER BY create_time DESC LIMIT ?";
        return jdbc.query(sql, new BeanPropertyRowMapper<>(AiChatHistory.class), userId, limit);
    }

    /**
     * 查用户的对话列表：每个 conversation_id 一行，含预览和统计。
     * 为什么用子查询取首条用户消息？—— GROUP BY 聚合后直接拿不到单条内容，
     * 用子查询取第一条 user 消息做预览，比 JOIN 更直观。
     */
    public List<Map<String, Object>> findConversationsByUserId(Long userId) {
        String sql = """
            SELECT
                c.conversation_id AS conversationId,
                (SELECT content FROM ai_chat_history
                 WHERE conversation_id = c.conversation_id AND role = 'user'
                 ORDER BY create_time ASC LIMIT 1) AS preview,
                COUNT(*) AS messageCount,
                MAX(create_time) AS updateTime
            FROM ai_chat_history c
            WHERE c.user_id = ?
            GROUP BY c.conversation_id
            ORDER BY MAX(c.create_time) DESC
            """;
        return jdbc.queryForList(sql, userId);
    }

    /**
     * 查某个对话的完整消息（按时间正序），给 Agent 恢复记忆用。
     * 为什么正序？—— Agent 需要按对话发生的先后顺序理解上下文。
     */
    public List<AiChatHistory> findByConversationId(String conversationId) {
        String sql = """
            SELECT id, user_id, conversation_id, role, content, create_time
            FROM ai_chat_history
            WHERE conversation_id = ?
            ORDER BY create_time ASC
            """;
        return jdbc.query(sql, new BeanPropertyRowMapper<>(AiChatHistory.class), conversationId);
    }

    /** 删除整个对话的所有消息 */
    public int deleteByConversationId(String conversationId) {
        String sql = "DELETE FROM ai_chat_history WHERE conversation_id = ?";
        return jdbc.update(sql, conversationId);
    }
}
