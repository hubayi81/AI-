package com.hubayi.aishoesrecommend.controller;

import com.hubayi.aishoesrecommend.common.Result;
import com.hubayi.aishoesrecommend.entity.ShoeProduct;
import com.hubayi.aishoesrecommend.entity.User;
import com.hubayi.aishoesrecommend.service.ShoeProductService;
import jakarta.servlet.http.HttpSession;
import org.springframework.web.bind.annotation.*;

/**
 * 管理员专用接口 —— 只有 role=admin 的用户能调用
 */
@RestController  //API 接口，返回 JSON
@RequestMapping("/api/admin/products")  //所有接口前缀都是：http://localhost:端口/api/admin/products
public class AdminProductController {

    private final ShoeProductService service;

    public AdminProductController(ShoeProductService service) {
        this.service = service;
    }

    // 每个方法开头校验管理员权限
    private Result<String> checkAdmin(HttpSession session) {
        User user = (User) session.getAttribute("user");
        if (user == null) return Result.error(401, "请先登录");
        if (!"admin".equals(user.getRole())) return Result.error(403, "需要管理员权限");
        return null;
    }//检查当前登录的人是不是管理员
//    从会话（session）里拿登录的用户
//    没登录 → 返回 401
//    登录了但角色不是 admin → 返回 403
//    是管理员 → 返回 null（表示校验通过）


    // 新增
    @PostMapping
    public Result<ShoeProduct> add(@RequestBody ShoeProduct p, HttpSession session) {
        Result<String> err = checkAdmin(session);
        if (err != null) return Result.error(err.getCode(), err.getMessage());
        ShoeProduct saved = service.addProduct(p);
        return Result.success(saved);
    }

    // 更新
    @PutMapping("/{id}")
    public Result<ShoeProduct> update(@PathVariable Long id, @RequestBody ShoeProduct p, HttpSession session) {
        Result<String> err = checkAdmin(session);
        if (err != null) return Result.error(err.getCode(), err.getMessage());
        p.setId(id);
        ShoeProduct updated = service.updateProduct(p);
        return Result.success(updated);
    }

    // 删除
    @DeleteMapping("/{id}")
    public Result<String> delete(@PathVariable Long id, HttpSession session) {
        Result<String> err = checkAdmin(session);
        if (err != null) return Result.error(err.getCode(), err.getMessage());
        service.deleteProduct(id);
        return Result.success("已删除");
    }
}
