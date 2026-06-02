package com.hubayi.aishoesrecommend.entity;

import java.time.LocalDateTime;

/**
 * 用户收藏
 */
public class Favorite {

    private Long id;
    private Long userId;
    private Long productId;
    private LocalDateTime createTime;

    public Favorite() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Long getUserId() { return userId; }
    public void setUserId(Long userId) { this.userId = userId; }

    public Long getProductId() { return productId; }
    public void setProductId(Long productId) { this.productId = productId; }

    public LocalDateTime getCreateTime() { return createTime; }
    public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }
}
