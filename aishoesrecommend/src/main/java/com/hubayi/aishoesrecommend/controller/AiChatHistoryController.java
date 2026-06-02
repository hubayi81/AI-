package com.hubayi.aishoesrecommend.controller;

import com.hubayi.aishoesrecommend.common.Result;
import com.hubayi.aishoesrecommend.dao.AiChatHistoryDao;
import com.hubayi.aishoesrecommend.entity.AiChatHistory;
import com.hubayi.aishoesrecommend.entity.User;
import jakarta.servlet.http.HttpSession;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * AI 对话历史接口 —— 需要登录才能访问
 */
@RestController
@RequestMapping("/api/user")
public class AiChatHistoryController {

    private final AiChatHistoryDao dao;

    public AiChatHistoryController(AiChatHistoryDao dao) {
        this.dao = dao;
    }

    private User currentUser(HttpSession session) {
        return (User) session.getAttribute("user");
    }

    /**
     * 保存一对对话（用户消息 + AI 回复）。
     * 为什么前端发一次请求存两条？—— 减少 HTTP 调用次数，且保证原子性：
     * 要存就一对都存上，不会出现只存了问没存答的脏数据。
     */
    @PostMapping("/ai-history")
    public Result<String> save(@RequestBody Map<String, String> body, HttpSession session) {
        User user = currentUser(session);
        if (user == null) return Result.error(401, "请先登录");

        Long userId = user.getId();
        String conversationId = body.getOrDefault("conversation_id", "");
        String userMsg = body.getOrDefault("user_message", "");
        String aiReply = body.getOrDefault("ai_reply", "");

        // 各存一条，role 区分
        if (!userMsg.isBlank()) {
            dao.insert(userId, conversationId, "user", userMsg);
        }
        if (!aiReply.isBlank()) {
            dao.insert(userId, conversationId, "ai", aiReply);
        }
        return Result.success("已保存");
    }

    /** 查最近 N 条 AI 对话历史（默认 50） */
    @GetMapping("/ai-history")
    public Result<List<AiChatHistory>> list(@RequestParam(defaultValue = "50") int limit,
                                            HttpSession session) {
        User user = currentUser(session);
        if (user == null) return Result.error(401, "请先登录");
        List<AiChatHistory> list = dao.findByUserId(user.getId(), limit);
        return Result.success(list);
    }
}
