package com.hubayi.aishoesrecommend.dao;

import com.hubayi.aishoesrecommend.entity.ShoeProduct;
import org.springframework.jdbc.core.BeanPropertyRowMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

@Repository
public class ShoeProductDao {

    private final JdbcTemplate jdbc;

    // 构造器注入，Spring 自动把 JdbcTemplate 传进来
    public ShoeProductDao(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    // 查全部商品
    public List<ShoeProduct> findAll() {
        String sql = "SELECT id,name,brand,gender,category,price,image_url,stock,description,color,size_range,create_time FROM shoe_product";
        return jdbc.query(sql, new BeanPropertyRowMapper<>(ShoeProduct.class));
    }

    // 根据ID查单个商品
    public ShoeProduct findById(Long id) {
        String sql = "SELECT id,name,brand,gender,category,price,image_url,stock,description,color,size_range,create_time FROM shoe_product WHERE id = ?";
        List<ShoeProduct> list = jdbc.query(sql, new BeanPropertyRowMapper<>(ShoeProduct.class), id);
        return list.isEmpty() ? null : list.get(0);
    }

    // 推荐查询：用户填了哪个条件就加哪个，没填的跳过
    public List<ShoeProduct> findByPreferences(String gender, String category, String brand,
                                               BigDecimal minPrice, BigDecimal maxPrice) {
        StringBuilder sql = new StringBuilder(
                "SELECT id,name,brand,gender,category,price,image_url,stock,description,color,size_range,create_time FROM shoe_product WHERE 1=1 ");
        List<Object> params = new ArrayList<>();

        if (gender != null && !gender.isBlank()) {
            sql.append("AND gender = ? ");
            params.add(gender);
        }
        if (category != null && !category.isBlank()) {
            sql.append("AND category = ? ");
            params.add(category);
        }
        if (brand != null && !brand.isBlank()) {
            sql.append("AND brand = ? ");
            params.add(brand);
        }
        if (minPrice != null) {
            sql.append("AND price >= ? ");
            params.add(minPrice);
        }
        if (maxPrice != null) {
            sql.append("AND price <= ? ");
            params.add(maxPrice);
        }
        sql.append("ORDER BY create_time DESC");

        return jdbc.query(sql.toString(), new BeanPropertyRowMapper<>(ShoeProduct.class), params.toArray());
    }
}