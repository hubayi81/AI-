package com.hubayi.aishoesrecommend.client;

import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Component
public class AiAgentClient {

    private final RestTemplate rest;

    private static final String AGENT_URL = "http://127.0.0.1:5000/api/ai/agent/chat";
    private static final String HEALTH_URL = "http://127.0.0.1:5000/health";

    public AiAgentClient() {
        this.rest = new RestTemplate();
    }

    /**
     * 发送对话请求给 Python Agent
     */
    public AiChatResponse chat(String conversationId, String message,
                               List<Map<String, Object>> products) {
        try {
            // 拼接请求体
            Map<String, Object> body = new HashMap<>();
            body.put("conversation_id", conversationId);
            body.put("message", message);
            body.put("products", products);

            // 发送 POST 请求，RestTemplate 自动处理 JSON 序列化
            return rest.postForObject(AGENT_URL, body, AiChatResponse.class);

        } catch (Exception e) {
            // AI 服务挂了，降级话术
            AiChatResponse fallback = new AiChatResponse();
            fallback.setConversationId(conversationId);
            fallback.setReply("AI 暂时不可用，请使用传统筛选模式。");
            fallback.setAction("chat");
            fallback.setResults(null);
            return fallback;
        }
    }

    /**
     * 检查 Python Agent 是否在线
     */
    public boolean health() {
        try {
            Map<?, ?> response = rest.getForObject(HEALTH_URL, Map.class);
            return response != null && "ok".equals(response.get("status"));
        } catch (Exception e) {
            return false;
        }
    }
}
