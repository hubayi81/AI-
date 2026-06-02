package com.hubayi.aishoesrecommend.controller;

import com.hubayi.aishoesrecommend.common.Result;
import com.hubayi.aishoesrecommend.entity.User;
import com.hubayi.aishoesrecommend.service.UserService;
import jakarta.servlet.http.HttpSession;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/user")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    // 注册
    @PostMapping("/register")
    public Result<String> register(@RequestParam String username,
                                   @RequestParam String password) {
        String error = userService.register(username, password);
        if (error != null) {
            return Result.error(400, error);
        }
        return Result.success("注册成功");
    }

    // 登录：isAdmin 参数来自前端"管理员登录"开关
    @PostMapping("/login")
    public Result<String> login(@RequestParam String username,
                                @RequestParam String password,
                                @RequestParam(defaultValue = "false") boolean isAdmin,
                                HttpSession session) {
        User user = userService.login(username, password, isAdmin);
        if (user == null) {
            // 管理员登录失败给更明确的提示
            String msg = isAdmin ? "用户名或密码错误，或非管理员账号" : "用户名或密码错误";
            return Result.error(401, msg);
        }
        session.setAttribute("user", user);
        return Result.success("登录成功");
    }

    // 检查登录状态
    @GetMapping("/status")
    public Result<User> status(HttpSession session) {
        User user = (User) session.getAttribute("user");
        if (user == null) {
            return Result.error(401, "未登录");
        }
        return Result.success(user);
    }

    // 退出登录
    @PostMapping("/logout")
    public Result<String> logout(HttpSession session) {
        session.removeAttribute("user");
        return Result.success("已退出");
    }
}