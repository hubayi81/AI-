package com.hubayi.aishoesrecommend.dao;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.sql.PreparedStatement;
import java.sql.Statement;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;

@Repository
public class FeedbackDao {

    private final JdbcTemplate jdbc;

    public FeedbackDao(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /**
     * ai_reply 的 SHA-256，作为"这条 AI 消息"的稳定身份。
     * <p>
     * 为什么需要它？—— 旧实现的去重键是 (user_id, conversation_id)，
     * 意味着一个会话里只能存活一条反馈：用户先给第 1 条回复点赞、
     * 再给第 5 条点踩，第 1 条的反馈会被 DELETE 掉。
     * 反馈数据被自己的写入逻辑吃掉了，所谓"数据飞轮"根本转不起来。
     * <p>
     * 为什么不用消息下标？—— 前端刷新或加载历史后下标会重排，
     * 同一个下标在不同时刻指向不同消息，会把反馈串到错误的回复上。
     * 回复内容本身才是稳定标识。
     */
    public static String replyHash(String aiReply) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] d = md.digest((aiReply == null ? "" : aiReply).getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(d);
        } catch (Exception e) {
            // SHA-256 是 JDK 必备算法，走不到这里；兜底退化成长度+hashCode，不抛异常打断用户操作
            return "fallback-" + (aiReply == null ? 0 : aiReply.hashCode());
        }
    }

    /**
     * 保存反馈（消息级覆盖）+ 归因到被推荐的商品。
     * <p>
     * 事务边界：主表 + 明细表必须同生共死。
     * 如果只写成功主表，聚合侧就会少算这批商品的反馈，
     * 排序权重被静默污染且无法自愈——这种错误没有报警、只会让推荐慢慢变差。
     *
     * @param productIds 本次 AI 回复中实际展示的商品 id 列表，可为空（非推荐类回复）
     * @return 主表反馈记录 id
     */
    @Transactional
    public long save(Long userId, String conversationId,
                     String userMessage, String aiReply, String feedback,
                     List<Long> productIds) {
        String hash = replyHash(aiReply);

        // 消息级覆盖：同一用户 + 同一会话 + 同一条回复，后提交的覆盖先前的
        Long oldId = jdbc.query(
                "SELECT id FROM ai_feedback WHERE user_id = ? AND conversation_id = ? AND reply_hash = ?",
                rs -> rs.next() ? rs.getLong(1) : null,
                userId, conversationId, hash);
        if (oldId != null) {
            jdbc.update("DELETE FROM ai_feedback_item WHERE feedback_id = ?", oldId);
            jdbc.update("DELETE FROM ai_feedback WHERE id = ?", oldId);
        }

        KeyHolder kh = new GeneratedKeyHolder();
        jdbc.update(con -> {
            PreparedStatement ps = con.prepareStatement(
                    "INSERT INTO ai_feedback(user_id, conversation_id, reply_hash, user_message, ai_reply, feedback) "
                            + "VALUES (?,?,?,?,?,?)",
                    Statement.RETURN_GENERATED_KEYS);
            ps.setLong(1, userId);
            ps.setString(2, conversationId);
            ps.setString(3, hash);
            ps.setString(4, userMessage);
            ps.setString(5, aiReply);
            ps.setString(6, feedback);
            return ps;
        }, kh);

        long feedbackId = kh.getKey() == null ? 0L : kh.getKey().longValue();

        if (feedbackId > 0 && productIds != null && !productIds.isEmpty()) {
            List<Object[]> batch = productIds.stream()
                    .filter(pid -> pid != null && pid > 0)
                    .distinct()
                    .map(pid -> new Object[]{feedbackId, userId, pid, feedback})
                    .toList();
            if (!batch.isEmpty()) {
                jdbc.batchUpdate(
                        "INSERT INTO ai_feedback_item(feedback_id, user_id, product_id, feedback) VALUES (?,?,?,?)",
                        batch);
            }
        }
        return feedbackId;
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

    /**
     * 按商品聚合好评/差评数，供运营查看"哪些鞋被点赞最多"。
     * 排序侧（Python）不走这个接口，它直接查同一张表做贝叶斯平滑，
     * 避免两个服务对同一份数据算出两套口径。
     */
    public List<Map<String, Object>> statsByProduct(int limit) {
        String sql = """
            SELECT i.product_id AS productId,
                   p.name AS name,
                   SUM(i.feedback = 'like') AS likes,
                   SUM(i.feedback = 'dislike') AS dislikes
            FROM ai_feedback_item i
            LEFT JOIN shoe_product p ON p.id = i.product_id
            GROUP BY i.product_id, p.name
            ORDER BY likes DESC, dislikes ASC
            LIMIT ?
            """;
        return jdbc.queryForList(sql, limit);
    }
}
