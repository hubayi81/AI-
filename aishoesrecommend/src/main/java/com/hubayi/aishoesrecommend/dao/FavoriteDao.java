package com.hubayi.aishoesrecommend.dao;

import com.hubayi.aishoesrecommend.entity.Favorite;
import org.springframework.jdbc.core.BeanPropertyRowMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public class FavoriteDao {

    private final JdbcTemplate jdbc;

    public FavoriteDao(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** 查用户所有收藏 */
    public List<Favorite> findByUserId(Long userId) {
        String sql = "SELECT id, user_id, product_id, create_time FROM favorite WHERE user_id = ? ORDER BY create_time DESC";
        return jdbc.query(sql, new BeanPropertyRowMapper<>(Favorite.class), userId);
    }

    /** 添加收藏。INSERT IGNORE 防止重复插入时报错，用户体验更好（点两次也不会崩） */
    public int insert(Long userId, Long productId) {
        String sql = "INSERT IGNORE INTO favorite(user_id, product_id) VALUES (?, ?)";
        return jdbc.update(sql, userId, productId);
    }

    /** 取消收藏 */
    public int delete(Long userId, Long productId) {
        String sql = "DELETE FROM favorite WHERE user_id = ? AND product_id = ?";
        return jdbc.update(sql, userId, productId);
    }
}
