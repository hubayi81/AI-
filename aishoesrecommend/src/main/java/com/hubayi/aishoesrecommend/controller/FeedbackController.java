package com.hubayi.aishoesrecommend.controller;

import com.hubayi.aishoesrecommend.common.Result;
import com.hubayi.aishoesrecommend.dao.FeedbackDao;
import com.hubayi.aishoesrecommend.entity.User;
import jakarta.servlet.http.HttpSession;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * AI 回复反馈接口。
 * <p>
 * 每个用户对**每条** AI 回复留一个反馈（like / dislike），后提交的覆盖先前的。
 * 去重粒度是"消息"而不是"会话"——旧版按会话去重会让同一会话里的早期反馈被删掉。
 * <p>
 * 反馈同时归因到本次推荐展示的商品（product_ids），
 * 排序侧据此计算商品级好评率并回灌到推荐评分，形成闭环。
 * 没有 product_ids 的反馈（如纯闲聊回复）只进主表，不参与排序。
 */
@RestController
@RequestMapping("/api/user")
public class FeedbackController {

    private final FeedbackDao dao;

    public FeedbackController(FeedbackDao dao) {
        this.dao = dao;
    }

    @PostMapping("/feedback")
    public Result<String> submit(@RequestBody Map<String, Object> body, HttpSession session) {
        User user = (User) session.getAttribute("user");
        if (user == null) return Result.error(401, "请先登录");

        String conversationId = str(body.get("conversation_id"));
        String userMessage = str(body.get("user_message"));
        String aiReply = str(body.get("ai_reply"));
        String feedback = str(body.get("feedback")); // "like" 或 "dislike"

        if (!"like".equals(feedback) && !"dislike".equals(feedback)) {
            return Result.error(400, "feedback 必须是 like 或 dislike");
        }

        dao.save(user.getId(), conversationId, userMessage, aiReply, feedback,
                parseProductIds(body.get("product_ids")));
        return Result.success("感谢反馈");
    }

    /**
     * 商品级反馈统计，给运营/演示看"哪些鞋口碑最好"。
     * 只读接口，登录即可访问。
     */
    @GetMapping("/feedback/stats")
    public Result<List<Map<String, Object>>> stats(@RequestParam(defaultValue = "20") int limit,
                                                   HttpSession session) {
        User user = (User) session.getAttribute("user");
        if (user == null) return Result.error(401, "请先登录");
        return Result.success(dao.statsByProduct(Math.min(Math.max(limit, 1), 100)));
    }

    private static String str(Object o) {
        return o == null ? "" : String.valueOf(o);
    }

    /**
     * 前端传来的 product_ids 是 JSON 数组，Jackson 反序列化成 List&lt;Integer&gt;。
     * 这里逐个安全转换：脏数据（null / 非数字 / 负数）直接跳过，
     * 不能因为一个坏 id 就让整条反馈写入失败——反馈是尽力而为的旁路数据。
     */
    private static List<Long> parseProductIds(Object raw) {
        List<Long> ids = new ArrayList<>();
        if (!(raw instanceof List<?> list)) return ids;
        for (Object o : list) {
            if (o == null) continue;
            try {
                long v = (o instanceof Number n) ? n.longValue() : Long.parseLong(String.valueOf(o).trim());
                if (v > 0) ids.add(v);
            } catch (NumberFormatException ignored) {
                // 跳过脏数据
            }
        }
        return ids;
    }
}
