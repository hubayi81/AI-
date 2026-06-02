package com.hubayi.aishoesrecommend.controller;

import com.hubayi.aishoesrecommend.client.AiAgentClient;
import com.hubayi.aishoesrecommend.client.AiChatRequest;
import com.hubayi.aishoesrecommend.client.AiChatResponse;
import com.hubayi.aishoesrecommend.common.Result;
import com.hubayi.aishoesrecommend.dao.FavoriteDao;
import com.hubayi.aishoesrecommend.entity.Favorite;
import com.hubayi.aishoesrecommend.entity.ShoeProduct;
import com.hubayi.aishoesrecommend.entity.User;
import com.hubayi.aishoesrecommend.service.ShoeProductService;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.*;

@RestController
public class ShoeProductController {

    private final ShoeProductService service;
    private final AiAgentClient aiAgentClient;
    private final FavoriteDao favoriteDao;

    public ShoeProductController(ShoeProductService service, AiAgentClient aiAgentClient,
                                 FavoriteDao favoriteDao) {
        this.service = service;
        this.aiAgentClient = aiAgentClient;
        this.favoriteDao = favoriteDao;
    }

    // 查全部商品
    @GetMapping("/api/products")
    public Result<List<ShoeProduct>> listAll() {
        List<ShoeProduct> list = service.getAllProducts();
        return Result.success(list);
    }

    // 根据ID查单个
    @GetMapping("/api/products/{id}")
    public Result<ShoeProduct> getById(@PathVariable Long id) {
        ShoeProduct p = service.getProductById(id);
        if (p == null) {
            return Result.error(404, "商品不存在");
        }
        return Result.success(p);
    }

    // 推荐查询
    @GetMapping("/api/products/recommend")
    public Result<List<ShoeProduct>> recommend(
            @RequestParam(required = false) String gender,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String brand,
            @RequestParam(required = false) BigDecimal minPrice,
            @RequestParam(required = false) BigDecimal maxPrice) {

        List<ShoeProduct> result = service.recommend(gender, category, brand, minPrice, maxPrice);
        if (result.isEmpty()) {
            return Result.success("暂无匹配的鞋款", result);
        }
        return Result.success(result);
    }

    // ===== AI 对话入口（非流式）=====
    @PostMapping("/api/ai/chat")
    public Result<AiChatResponse> aiChat(@RequestBody AiChatRequest req, HttpSession session) {
        List<ShoeProduct> products = service.getAllProducts();
        List<Map<String, Object>> productMaps = toProductMaps(products);

        // 根据用户收藏计算画像，使 AI 推荐更个性化
        String userContext = buildUserContext(session);

        AiChatResponse resp = aiAgentClient.chat(
                req.getConversationId(), req.getMessage(), productMaps, userContext);

        return Result.success(resp);
    }

    // AI 健康检查
    @GetMapping("/api/ai/health")
    public Result<Map<String, Boolean>> aiHealth() {
        boolean online = aiAgentClient.health();
        return Result.success(Map.of("online", online));
    }

    // ===== AI 流式对话入口（SSE 透传 Python）=====
    @PostMapping("/api/ai/chat/stream")
    public void aiChatStream(@RequestBody AiChatRequest req,
                             HttpServletResponse response,
                             HttpSession session) {
        List<ShoeProduct> products = service.getAllProducts();
        List<Map<String, Object>> productMaps = toProductMaps(products);

        // 根据用户收藏计算画像
        String userContext = buildUserContext(session);

        aiAgentClient.chatStream(req.getConversationId(), req.getMessage(),
                productMaps, userContext, response);
    }

    // ---- 工具方法 ----

    /** 商品实体列表 → Map 列表（给 Python 用的标准格式） */
    private List<Map<String, Object>> toProductMaps(List<ShoeProduct> products) {
        return products.stream().map(p -> {
            Map<String, Object> map = new LinkedHashMap<>();
            map.put("id", p.getId());
            map.put("name", p.getName());
            map.put("brand", p.getBrand());
            map.put("category", p.getCategory());
            map.put("gender", p.getGender());
            map.put("price", p.getPrice());
            map.put("description", p.getDescription());
            map.put("color", p.getColor());
            map.put("sizeRange", p.getSizeRange());
            map.put("stock", p.getStock());
            map.put("imageUrl", p.getImageUrl());
            return map;
        }).toList();
    }

    /**
     * 根据用户收藏记录生成画像文本，传递给 AI 做个性化推荐。
     * 未登录时返回空字符串，AI 正常推荐（无个性化）。
     * 为什么只统计收藏？—— 收藏 = 用户明确表达的兴趣，比浏览行为更可靠。
     */
    private String buildUserContext(HttpSession session) {
        User user = (User) session.getAttribute("user");
        if (user == null) return "";

        List<Favorite> favs = favoriteDao.findByUserId(user.getId());
        if (favs.isEmpty()) return "";

        // 根据收藏的 productId 找到对应商品
        List<ShoeProduct> allProducts = service.getAllProducts();
        Map<Long, ShoeProduct> productMap = new HashMap<>();
        for (ShoeProduct p : allProducts) {
            productMap.put(p.getId(), p);
        }

        // 统计收藏偏好
        Set<String> favBrands = new LinkedHashSet<>();
        Set<String> favCategories = new LinkedHashSet<>();
        double totalPrice = 0;
        int count = 0;

        for (Favorite f : favs) {
            ShoeProduct p = productMap.get(f.getProductId());
            if (p != null) {
                if (p.getBrand() != null) favBrands.add(p.getBrand());
                if (p.getCategory() != null) favCategories.add(p.getCategory());
                if (p.getPrice() != null) {
                    totalPrice += p.getPrice().doubleValue();
                    count++;
                }
            }
        }

        // 拼成自然语言，注入系统提示词
        StringBuilder ctx = new StringBuilder();
        ctx.append("该用户画像：");
        if (!favBrands.isEmpty()) {
            ctx.append("偏好品牌 ").append(String.join("、", favBrands)).append("；");
        }
        if (!favCategories.isEmpty()) {
            ctx.append("偏好鞋类 ").append(String.join("、", favCategories)).append("；");
        }
        if (count > 0) {
            double avgPrice = totalPrice / count;
            ctx.append("平均收藏价位约 ¥").append(String.format("%.0f", avgPrice)).append("；");
        }
        ctx.append("共收藏 ").append(favs.size()).append(" 双鞋。");
        ctx.append("推荐时可以优先考虑这些偏好，但不要刻意提'画像'两个字。");

        return ctx.toString();
    }
}
