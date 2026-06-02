package com.hubayi.aishoesrecommend.service;

import com.hubayi.aishoesrecommend.dao.FavoriteDao;
import com.hubayi.aishoesrecommend.entity.Favorite;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class FavoriteService {

    private final FavoriteDao dao;

    public FavoriteService(FavoriteDao dao) {
        this.dao = dao;
    }

    public List<Favorite> getFavorites(Long userId) {
        return dao.findByUserId(userId);
    }

    public void addFavorite(Long userId, Long productId) {
        dao.insert(userId, productId);
    }

    public void removeFavorite(Long userId, Long productId) {
        dao.delete(userId, productId);
    }
}
