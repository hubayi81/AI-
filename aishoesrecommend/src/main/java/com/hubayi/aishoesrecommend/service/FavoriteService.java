package com.hubayi.aishoesrecommend.service;

import com.hubayi.aishoesrecommend.dao.FavoriteDao;
import com.hubayi.aishoesrecommend.entity.Favorite;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
public class FavoriteService {

    private final FavoriteDao dao;

    public FavoriteService(FavoriteDao dao) {
        this.dao = dao;
    }

    public List<Favorite> getFavorites(Long userId) {
        return dao.findByUserId(userId);
    }

    /** 获取收藏列表（含商品信息），前端一个请求搞定，不再需要调两次接口 */
    public List<Map<String, Object>> getFavoritesWithProduct(Long userId) {
        return dao.findFavoritesWithProduct(userId);
    }

    public void addFavorite(Long userId, Long productId) {
        dao.insert(userId, productId);
    }

    public void removeFavorite(Long userId, Long productId) {
        dao.delete(userId, productId);
    }
}
