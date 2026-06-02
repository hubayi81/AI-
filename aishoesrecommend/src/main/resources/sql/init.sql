CREATE DATABASE aishoes CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE aishoes

DROP TABLE IF EXISTS shoe_product;
                                                                                                                                                                                            
CREATE TABLE shoe_product (
      id          BIGINT          AUTO_INCREMENT PRIMARY KEY COMMENT '商品ID',
      name        VARCHAR(200)    NOT NULL COMMENT '商品名称',
      brand       VARCHAR(100)    NOT NULL COMMENT '品牌',
      gender      VARCHAR(10)     NOT NULL COMMENT '适用性别: male/female/unisex',
      category    VARCHAR(50)     NOT NULL COMMENT '鞋类: 运动鞋/休闲鞋/篮球鞋/跑鞋/板鞋/帆布鞋',
      price       DECIMAL(10, 2)  NOT NULL COMMENT '价格(元)',
      image_url   VARCHAR(500)    DEFAULT NULL COMMENT '商品图片URL',
      stock       INT             DEFAULT 0 COMMENT '库存数量',
      description TEXT            DEFAULT NULL COMMENT '商品描述',
      color       VARCHAR(50)     DEFAULT NULL COMMENT '颜色',
      size_range  VARCHAR(50)     DEFAULT NULL COMMENT '尺码范围，如 36-44',
      create_time DATETIME        DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='鞋类商品表';

  INSERT INTO shoe_product (name, brand, gender, category, price, image_url, stock, description, color, size_range) VALUES
  ('Air Max 270',          'Nike',     'male',   '运动鞋', 899.00,  '/images/nike-airmax270.jpg',   100, '经典气垫运动鞋，舒适缓震',            '黑色', '39-45'),
  ('Ultraboost 23',        'Adidas',   'male',   '跑鞋',   1099.00, '/images/adidas-ultraboost.jpg', 80,  'Boost中底科技，能量反馈跑鞋',          '白色', '39-44'),
  ('Chuck Taylor All Star', 'Converse', 'unisex', '帆布鞋', 499.00,  '/images/converse-chuck.jpg',    150, '经典帆布鞋，百搭单品',                 '米白', '35-43'),
  ('Old Skool',            'Vans',     'unisex', '板鞋',   569.00,  '/images/vans-oldskool.jpg',     120, '标志性侧边条纹，街头风格',            '黑白', '35-44'),
  ('Air Jordan 1 Low',     'Nike',     'male',   '篮球鞋', 999.00,  '/images/nike-aj1low.jpg',       60,  '飞人经典低帮款，复古篮球鞋',          '红黑', '39-45'),
  ('Cloudmonster',         'On',       'female', '跑鞋',   1299.00, '/images/on-cloudmonster.jpg',   40,  '瑞士On跑鞋，极致缓震',                '白紫', '35-40'),
  ('Gazelle Bold',         'Adidas',   'female', '休闲鞋', 799.00,  '/images/adidas-gazelle.jpg',    90,  '厚底增高休闲鞋，时尚复古',            '粉色', '35-39'),
  ('Classic Clog',         'Crocs',    'unisex', '休闲鞋', 399.00,  '/images/crocs-classic.jpg',     200, '轻便洞洞鞋，清凉一夏',                '白色', '36-45'),
  ('Dunk Low',             'Nike',     'female', '运动鞋', 749.00,  '/images/nike-dunklow.jpg',      70,  '复古Dunk系列，配色清新百搭',          '浅蓝', '35.5-40'),
  ('Gel-Kayano 30',        'Asics',    'male',   '跑鞋',   1190.00, '/images/asics-kayano.jpg',      50,  '亚瑟士稳定支撑跑鞋，长跑利器',        '深蓝', '39-45');
  
  
  CREATE TABLE user (                                                                                                                                              id          BIGINT          AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID',
      username    VARCHAR(50)     NOT NULL UNIQUE COMMENT '用户名',                                                                                          
      password    VARCHAR(200)    NOT NULL COMMENT '密码（BCrypt加密存储）',
      create_time DATETIME        DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间'
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';
  SELECT * FROM user
  
  
  
ALTER TABLE `user` ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user' AFTER password;

-- 给已有的用户设角色（把你自己设成管理员）
UPDATE `user` SET role = 'admin' WHERE username = '你的用户名';

-- 验证
SELECT id, username, role FROM `user`;

-- 给已有的用户设角色（把admin设成管理员）
UPDATE `user` SET role = 'admin' WHERE username = 'admin';
-- 验证
SELECT id, username, role FROM `user`;


-- 收藏表
CREATE TABLE favorite (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_product (user_id, product_id)
);

-- AI 对话历史表
CREATE TABLE ai_chat_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    conversation_id VARCHAR(50),
    role VARCHAR(20) NOT NULL,
    content TEXT,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 用户对 AI 推荐的反馈表
CREATE TABLE ai_feedback (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    conversation_id VARCHAR(50),
    user_message TEXT COMMENT '用户当时的提问',
    ai_reply TEXT COMMENT 'AI 的回复',
    feedback VARCHAR(10) NOT NULL COMMENT 'like 或 dislike',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_conv (user_id, conversation_id)
);
