package com.hubayi.aishoesrecommend.controller;

import com.hubayi.aishoesrecommend.common.Result;
import com.hubayi.aishoesrecommend.entity.Favorite;
import com.hubayi.aishoesrecommend.entity.User;
import com.hubayi.aishoesrecommend.service.FavoriteService;
import jakarta.servlet.http.HttpSession;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 收藏接口。
 * 每个方法都独立校验登录，因为 HTTP 是无状态的——不能信任前端一定传了合法 session。
 */
@RestController
@RequestMapping("/api/user")
public class FavoriteController {

    private final FavoriteService service;

    public FavoriteController(FavoriteService service) {
        this.service = service;
    }

    /** 从 session 获取当前登录用户，未登录返回 null */
    private User currentUser(HttpSession session) {
        return (User) session.getAttribute("user");
    }

    /** 获取我的收藏列表 */
    @GetMapping("/favorites")
    public Result<List<Favorite>> list(HttpSession session) {
        User user = currentUser(session);
        if (user == null) return Result.error(401, "请先登录");
        List<Favorite> list = service.getFavorites(user.getId());
        return Result.success(list);
    }

    /** 添加收藏 */
    @PostMapping("/favorite/{productId}")
    public Result<String> add(@PathVariable Long productId, HttpSession session) {
        User user = currentUser(session);
        if (user == null) return Result.error(401, "请先登录");
        service.addFavorite(user.getId(), productId);
        return Result.success("已收藏");
    }

    /** 取消收藏 */
    @DeleteMapping("/favorite/{productId}")
    public Result<String> remove(@PathVariable Long productId, HttpSession session) {
        User user = currentUser(session);
        if (user == null) return Result.error(401, "请先登录");
        service.removeFavorite(user.getId(), productId);
        return Result.success("已取消收藏");
    }
}
