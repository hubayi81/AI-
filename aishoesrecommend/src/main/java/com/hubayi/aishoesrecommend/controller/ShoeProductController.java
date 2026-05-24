package com.hubayi.aishoesrecommend.controller;

import com.hubayi.aishoesrecommend.client.AiAgentClient;
import com.hubayi.aishoesrecommend.client.AiChatRequest;
import com.hubayi.aishoesrecommend.client.AiChatResponse;
import com.hubayi.aishoesrecommend.common.Result;
import com.hubayi.aishoesrecommend.entity.ShoeProduct;
import com.hubayi.aishoesrecommend.service.ShoeProductService;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
public class ShoeProductController {

    private final ShoeProductService service;
    private final AiAgentClient aiAgentClient;

    public ShoeProductController(ShoeProductService service, AiAgentClient aiAgentClient) {
        this.service = service;
        this.aiAgentClient = aiAgentClient;
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

    // ===== AI 对话入口 =====
    @PostMapping("/api/ai/chat")
    public Result<AiChatResponse> aiChat(@RequestBody AiChatRequest req) {
        // 1. 查全部商品
        List<ShoeProduct> products = service.getAllProducts();

        // 2. 转成 Map 列表（Python 那边 tools.py 用 .get() 读字段）
        List<Map<String, Object>> productMaps = products.stream().map(p -> {
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
            return map;
        }).toList();

        // 3. 调 Python Agent
        AiChatResponse resp = aiAgentClient.chat(
                req.getConversationId(), req.getMessage(), productMaps);

        return Result.success(resp);
    }

    // AI 健康检查
    @GetMapping("/api/ai/health")
    public Result<Map<String, Boolean>> aiHealth() {
        boolean online = aiAgentClient.health();
        return Result.success(Map.of("online", online));
    }
}
