package com.hubayi.aishoesrecommend.controller;

import com.hubayi.aishoesrecommend.common.Result;
import com.hubayi.aishoesrecommend.dao.FeedbackDao;
import com.hubayi.aishoesrecommend.entity.User;
import jakarta.servlet.http.HttpSession;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * AI 回复反馈接口。
 * 每个用户对每次 AI 回复只能留一个反馈（like / dislike），后提交的覆盖先前的。
 * 为什么需要这个？—— 积累真实用户反馈，后续可以分析"哪些推荐被点赞多"
 * 来持续优化系统提示词和推荐策略，这是推荐系统上线后的核心数据飞轮。
 */
@RestController
@RequestMapping("/api/user")
public class FeedbackController {

    private final FeedbackDao dao;

    public FeedbackController(FeedbackDao dao) {
        this.dao = dao;
    }

    @PostMapping("/feedback")
    public Result<String> submit(@RequestBody Map<String, String> body, HttpSession session) {
        User user = (User) session.getAttribute("user");
        if (user == null) return Result.error(401, "请先登录");

        String conversationId = body.getOrDefault("conversation_id", "");
        String userMessage = body.getOrDefault("user_message", "");
        String aiReply = body.getOrDefault("ai_reply", "");
        String feedback = body.getOrDefault("feedback", ""); // "like" 或 "dislike"

        if (!"like".equals(feedback) && !"dislike".equals(feedback)) {
            return Result.error(400, "feedback 必须是 like 或 dislike");
        }

        dao.save(user.getId(), conversationId, userMessage, aiReply, feedback);
        return Result.success("感谢反馈");
    }
}
