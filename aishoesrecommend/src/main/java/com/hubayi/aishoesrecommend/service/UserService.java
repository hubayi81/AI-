package com.hubayi.aishoesrecommend.service;

import com.hubayi.aishoesrecommend.dao.UserDao;
import com.hubayi.aishoesrecommend.entity.User;
import org.springframework.security.crypto.bcrypt.BCrypt;
import org.springframework.stereotype.Service;

@Service
public class UserService {

    private final UserDao userDao;

    public UserService(UserDao userDao) {
        this.userDao = userDao;
    }

    // 注册：返回 null 表示成功，返回字符串表示错误原因
    public String register(String username, String password) {
        if (username == null || username.isBlank()) {
            return "用户名不能为空";
        }
        if (password == null || password.length() < 6) {
            return "密码不能少于6位";
        }
        if (userDao.existsByUsername(username)) {
            return "用户名已存在";
        }

        User user = new User();
        user.setUsername(username);
        user.setPassword(BCrypt.hashpw(password, BCrypt.gensalt()));  // 加密存储
        userDao.insert(user);
        return null;  // null = 注册成功
    }

    // 登录：返回 null 表示失败，返回 User 表示成功
    public User login(String username, String password) {
        User user = userDao.findByUsername(username);
        if (user == null) {
            return null;
        }
        if (BCrypt.checkpw(password, user.getPassword())) {
            return user;
        }
        return null;
    }
}