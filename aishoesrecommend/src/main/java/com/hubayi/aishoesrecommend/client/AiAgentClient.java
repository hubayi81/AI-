package com.hubayi.aishoesrecommend.client;

import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.PrintWriter;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * AI 服务客户端 —— 调 Python FastAPI
 */
@Component
public class AiAgentClient {

    private final RestTemplate rest;

    private static final String AGENT_URL = "http://127.0.0.1:5000/api/ai/agent/chat";
    private static final String AGENT_STREAM_URL = "http://127.0.0.1:5000/api/ai/agent/chat/stream";
    private static final String HEALTH_URL = "http://127.0.0.1:5000/health";

    public AiAgentClient() {
        this.rest = new RestTemplate();
    }

    /**
     * 发送对话请求给 Python Agent（非流式，保留兼容）
     * @param userContext 用户画像（收藏偏好等），可为空
     * @param history 对话历史（role + content 列表），用于恢复 Agent 记忆
     */
    public AiChatResponse chat(String conversationId, String message,
                               List<Map<String, Object>> products,
                               String userContext,
                               List<Map<String, String>> history) {
        try {
            Map<String, Object> body = new HashMap<>();
            body.put("conversation_id", conversationId);
            body.put("message", message);
            body.put("products", products);
            // 用户画像传给 Python，使推荐更个性化（如收藏的鞋品牌/品类）
            body.put("user_context", userContext != null ? userContext : "");
            // 对话历史传给 Python 用于恢复记忆（Python 重启后也能接上）
            body.put("history", history != null ? history : List.of());

            return rest.postForObject(AGENT_URL, body, AiChatResponse.class);

        } catch (Exception e) {
            AiChatResponse fallback = new AiChatResponse();
            fallback.setConversationId(conversationId);
            fallback.setReply("AI 暂时不可用，请使用传统筛选模式。");
            fallback.setAction("chat");
            fallback.setResults(null);
            return fallback;
        }
    }

    /**
     * SSE 流式对话 —— 透传 Python 的 SSE 流到前端。
     * 用原生 HttpURLConnection 实现，因为 RestTemplate 会等完整响应才返回，不适合流式转发。
     * @param userContext 用户画像（收藏偏好等），可为空
     * @param history 对话历史（role + content 列表），用于恢复 Agent 记忆
     */
    public void chatStream(String conversationId, String message,
                           List<Map<String, Object>> products,
                           String userContext,
                           List<Map<String, String>> history,
                           HttpServletResponse response) {
        HttpURLConnection conn = null;
        try {
            // 1. 构建请求体 JSON（手写，避免引入 Jackson）
            StringBuilder json = new StringBuilder();
            json.append("{\"conversation_id\":");
            json.append(conversationId == null ? "null" : "\"" + escapeJson(conversationId) + "\"");
            json.append(",\"message\":\"").append(escapeJson(message)).append("\"");
            // 用户画像 —— 让 AI 了解用户偏好
            json.append(",\"user_context\":\"").append(escapeJson(userContext != null ? userContext : "")).append("\"");
            // 对话历史 —— Python 重启后从此恢复记忆，保证对话连续性
            json.append(",\"history\":[");
            if (history != null) {
                for (int i = 0; i < history.size(); i++) {
                    if (i > 0) json.append(",");
                    Map<String, String> msg = history.get(i);
                    json.append("{\"role\":\"").append(escapeJson(msg.get("role"))).append("\"");
                    json.append(",\"content\":\"").append(escapeJson(msg.get("content"))).append("\"}");
                }
            }
            json.append("]");
            json.append(",\"products\":[");
            for (int i = 0; i < products.size(); i++) {
                if (i > 0) json.append(",");
                json.append(productToJson(products.get(i)));
            }
            json.append("]}");

            // 2. 向 Python 发起 POST 请求
            URI uri = URI.create(AGENT_STREAM_URL);
            conn = (HttpURLConnection) uri.toURL().openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setDoOutput(true);
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(120000); // 流式读取，2 分钟超时

            byte[] reqBytes = json.toString().getBytes(StandardCharsets.UTF_8);
            try (OutputStream os = conn.getOutputStream()) {
                os.write(reqBytes);
                os.flush();
            }

            // 3. 设置前端响应头（SSE 格式）
            response.setContentType("text/event-stream");
            response.setCharacterEncoding("UTF-8");
            response.setHeader("Cache-Control", "no-cache");
            response.setHeader("Connection", "keep-alive");
            response.setHeader("X-Accel-Buffering", "no"); // 禁用 nginx 代理缓冲

            // 4. 逐行透传 Python 的 SSE 到前端
            PrintWriter writer = response.getWriter();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    writer.write(line);
                    writer.write("\n");
                    writer.flush();
                }
            }

        } catch (Exception e) {
            // 流失败时，向前端写一个降级 SSE 事件
            try {
                PrintWriter writer = response.getWriter();
                writer.write("data: {\"done\":true,\"reply\":\"AI 暂时不可用，请稍后再试。\",\"action\":\"chat\"}\n\n");
                writer.flush();
            } catch (Exception ignored) {}
        } finally {
            if (conn != null) conn.disconnect();
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

    // ---- 工具方法 ----

    /** 转义 JSON 字符串中的特殊字符 */
    private String escapeJson(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }

    /** 把商品 Map 转为 JSON 字符串（手写序列化以保持轻量，不引入 Jackson ObjectMapper） */
    private String productToJson(Map<String, Object> p) {
        StringBuilder sb = new StringBuilder("{");
        appendField(sb, "id", p.get("id"));
        appendField(sb, "name", p.get("name"));
        appendField(sb, "brand", p.get("brand"));
        appendField(sb, "gender", p.get("gender"));
        appendField(sb, "category", p.get("category"));
        appendField(sb, "price", p.get("price"));
        appendField(sb, "imageUrl", p.get("imageUrl"));
        appendField(sb, "stock", p.get("stock"));
        appendField(sb, "description", p.get("description"));
        appendField(sb, "color", p.get("color"));
        appendField(sb, "sizeRange", p.get("sizeRange"));
        // 去掉末尾逗号
        if (sb.charAt(sb.length() - 1) == ',') {
            sb.setLength(sb.length() - 1);
        }
        sb.append("}");
        return sb.toString();
    }

    private void appendField(StringBuilder sb, String key, Object value) {
        if (value == null) {
            sb.append("\"").append(key).append("\":null,");
        } else if (value instanceof Number) {
            sb.append("\"").append(key).append("\":").append(value).append(",");
        } else {
            sb.append("\"").append(key).append("\":\"").append(escapeJson(value.toString())).append("\",");
        }
    }
}
