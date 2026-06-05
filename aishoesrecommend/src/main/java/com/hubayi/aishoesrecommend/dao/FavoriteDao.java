package com.hubayi.aishoesrecommend.dao;

import com.hubayi.aishoesrecommend.entity.Favorite;
import org.springframework.jdbc.core.BeanPropertyRowMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Map;

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

    /**
     * 查用户收藏 + 关联商品信息（name/price/image/brand/category）。
     * 为什么用 JOIN 而不是两次查询？—— 前端个人中心每次打开都要等两次请求（收藏 + 全量商品），
     * JOIN 让 MySQL 一次返回所需全部数据，网络往返从 2 次减到 1 次，数据量从几百条减到收藏数。
     * 为什么返回 Map 而不是实体？—— 收藏和商品是两张表的字段拼在一起的，无对应实体，用 Map 最灵活。
     */
    public List<Map<String, Object>> findFavoritesWithProduct(Long userId) {
        String sql = """
            SELECT
                f.id, f.product_id AS productId, f.create_time AS createTime,
                p.name, p.brand, p.category, p.price, p.image_url AS imageUrl, p.gender
            FROM favorite f
            JOIN shoe_product p ON f.product_id = p.id
            WHERE f.user_id = ?
            ORDER BY f.create_time DESC
            """;
        return jdbc.queryForList(sql, userId);
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
