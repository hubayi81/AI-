package com.hubayi.aishoesrecommend.entity;

import java.time.LocalDateTime;

public class User {

    private Long id;
    private String username;
    private String password;     // 存的是 BCrypt 加密后的密文
    private LocalDateTime createTime;

    public User() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }

    public String getPassword() { return password; }
    public void setPassword(String password) { this.password = password; }

    public LocalDateTime getCreateTime() { return createTime; }
    public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }
}