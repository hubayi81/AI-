package com.hubayi.aishoesrecommend.dao;

import com.hubayi.aishoesrecommend.entity.User;
import org.springframework.jdbc.core.BeanPropertyRowMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public class UserDao {

    private final JdbcTemplate jdbc;

    public UserDao(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    // 根据用户名查用户（登录时用）
    public User findByUsername(String username) {
        String sql = "SELECT id, username, password, create_time FROM `user` WHERE username = ?";
        List<User> list = jdbc.query(sql, new BeanPropertyRowMapper<>(User.class), username);
        return list.isEmpty() ? null : list.get(0);
    }

    // 注册新用户
    public int insert(User user) {
        String sql = "INSERT INTO `user`(username, password) VALUES (?, ?)";
        return jdbc.update(sql, user.getUsername(), user.getPassword());
    }

    // 检查用户名是否已存在
    public boolean existsByUsername(String username) {
        String sql = "SELECT COUNT(*) FROM `user` WHERE username = ?";
        Integer count = jdbc.queryForObject(sql, Integer.class, username);
        return count != null && count > 0;
    }
}