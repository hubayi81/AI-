package com.hubayi.aishoesrecommend.service;

import com.hubayi.aishoesrecommend.dao.ShoeProductDao;
import com.hubayi.aishoesrecommend.entity.ShoeProduct;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.List;

@Service
public class ShoeProductService {

    private final ShoeProductDao dao;

    public ShoeProductService(ShoeProductDao dao) {
        this.dao = dao;
    }

    // 获取全部商品
    public List<ShoeProduct> getAllProducts() {
        return dao.findAll();
    }

    // 根据ID获取商品
    public ShoeProduct getProductById(Long id) {
        return dao.findById(id);
    }

    // 根据用户偏好推荐
    public List<ShoeProduct> recommend(String gender, String category, String brand,
                                       BigDecimal minPrice, BigDecimal maxPrice) {
        return dao.findByPreferences(gender, category, brand, minPrice, maxPrice);
    }
}