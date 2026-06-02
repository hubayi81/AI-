package com.hubayi.aishoesrecommend.dao;

import com.hubayi.aishoesrecommend.entity.AiChatHistory;
import org.springframework.jdbc.core.BeanPropertyRowMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;

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
}
