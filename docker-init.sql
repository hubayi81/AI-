-- Docker 自动初始化脚本（MySQL 容器首次启动时执行）
-- 放在 /docker-entrypoint-initdb.d/ 下自动运行

CREATE DATABASE IF NOT EXISTS aishoes CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE aishoes;

-- 商品表
CREATE TABLE IF NOT EXISTS shoe_product (
    id          BIGINT          AUTO_INCREMENT PRIMARY KEY COMMENT '商品ID',
    name        VARCHAR(200)    NOT NULL COMMENT '商品名称',
    brand       VARCHAR(100)    NOT NULL COMMENT '品牌',
    gender      VARCHAR(10)     NOT NULL COMMENT '适用性别: male/female/unisex',
    category    VARCHAR(50)     NOT NULL COMMENT '鞋类',
    price       DECIMAL(10, 2)  NOT NULL COMMENT '价格(元)',
    image_url   VARCHAR(500)    DEFAULT NULL COMMENT '商品图片URL',
    stock       INT             DEFAULT 0 COMMENT '库存数量',
    description TEXT            DEFAULT NULL COMMENT '商品描述',
    color       VARCHAR(50)     DEFAULT NULL COMMENT '颜色',
    size_range  VARCHAR(50)     DEFAULT NULL COMMENT '尺码范围',
    create_time DATETIME        DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='鞋类商品表';

-- 示例商品数据（半真实：真实品牌/型号/卖点/价位，手工整理，覆盖多足型多场景）
-- 与 ai-service/eval_catalog.py 的 15 款固定目录保持一致（id 1-15 对应），
-- 保证「线上演示目录」与「离线评测目录」同源，避免两套数据漂移。
INSERT INTO shoe_product (id, name, brand, gender, category, price, image_url, stock, description, color, size_range) VALUES
(1,  'Air Zoom Pegasus 41',   'Nike',      'male',   '跑鞋',   899.00,  '/images/nike-pegasus41.jpg',    100, '轻量缓震跑鞋，Zoom Air 气垫，适合日常训练和 5-10 公里路跑',       '黑色',   '39-45'),
(2,  'Ultraboost 5X',         'Adidas',    'unisex', '跑鞋',   1099.00, '/images/adidas-ultraboost5x.jpg', 80, 'Boost 中底全掌缓震，Primeknit 飞织鞋面，脚感软弹适合日常通勤和恢复跑', '白色', '39-44'),
(3,  'Gel-Kayano 30',         'Asics',     'male',   '跑鞋',   1190.00, '/images/asics-kayano30.jpg',     50, '支撑稳定型跑鞋，DUOMAX 双密度中底，适合扁平足和过度内旋跑者',     '深蓝',   '39-45'),
(4,  'Old Skool',             'Vans',      'unisex', '板鞋',   569.00,  '/images/vans-oldskool.jpg',     120, '经典侧边条纹板鞋，耐磨硫化底，街头滑板风格',                     '黑白',   '35-44'),
(5,  'Chuck Taylor All Star', 'Converse',  'unisex', '帆布鞋', 499.00,  '/images/converse-chuck.jpg',    150, '经典高帮帆布鞋，百搭单品，适合日常休闲',                         '米白',   '35-43'),
(6,  'Air Jordan 1 Low',      'Nike',      'male',   '篮球鞋', 999.00,  '/images/nike-aj1low.jpg',        60, '飞人经典低帮款，Air Sole 气垫，复古篮球鞋风格',                   '红黑',   '39-45'),
(7,  'Cloudmonster 2',        'On',        'unisex', '跑鞋',   1299.00, '/images/on-cloudmonster2.jpg',   40, 'CloudTec 镂空中底，极致缓震回弹，适合长距离路跑',                 '白紫',   '35-45'),
(8,  'Classic Clog',          'Crocs',     'unisex', '休闲鞋', 399.00,  '/images/crocs-classic.jpg',     200, '轻便洞洞鞋，Croslite 材质，透气不闷脚，夏天必备',                 '白色',   '36-45'),
(9,  'Dunk Low',              'Nike',      'female', '运动鞋', 749.00,  '/images/nike-dunklow.jpg',       70, '复古 Dunk 系列，配色清新百搭，适合日常通勤和逛街',               '浅蓝',   '35.5-40'),
(10, 'Gazelle Bold',          'Adidas',    'female', '休闲鞋', 799.00,  '/images/adidas-gazelle.jpg',     90, '厚底增高休闲鞋，翻毛皮鞋面，时尚复古风格',                       '粉色',   '35-39'),
(11, 'Fresh Foam X 1080v13',  'New Balance','unisex', '跑鞋',  999.00,  '/images/nb-1080v13.jpg',         60, 'Fresh Foam X 顶级缓震中底，宽楦版本可选 2E/4E，适合宽脚跑者',     '灰色',   '38-45'),
(12, 'Adizero SL',            'Adidas',    'male',   '竞速跑鞋', 699.00, '/images/adidas-adizero-sl.jpg',  70, 'Lightstrike Pro 中底，轻量竞速训练鞋，适合速度训练和比赛',       '荧光绿', '39-45'),
(13, 'Gel-Nimbus 26',         'Asics',     'female', '跑鞋',   1290.00, '/images/asics-nimbus26.jpg',     50, 'PureGEL 顶级缓震，FF BLAST+ 中底，适合高足弓和需要软底的人群',   '米白',   '35-40'),
(14, 'Speedcat OG',           'Puma',      'unisex', '板鞋',   699.00,  '/images/puma-speedcat.jpg',      80, '复古赛车鞋薄底设计，翻毛皮+皮革拼接，适合窄脚瘦脚人群',           '红黑',   '36-44'),
(15, 'Go Walk 7',             'Skechers',  'unisex', '健步鞋', 599.00,  '/images/skechers-gowalk7.jpg',   90, 'Hyper Burst 超轻中底，一脚蹬设计，适合日常走路和久站',           '黑色',   '36-45');

-- 用户表
CREATE TABLE IF NOT EXISTS user (
    id          BIGINT          AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID',
    username    VARCHAR(50)     NOT NULL UNIQUE COMMENT '用户名',
    password    VARCHAR(200)    NOT NULL COMMENT '密码（BCrypt加密存储）',
    role        VARCHAR(20)     NOT NULL DEFAULT 'user' COMMENT '角色: user/admin',
    create_time DATETIME        DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- 管理员账号（密码 123456 的 BCrypt 哈希）
INSERT IGNORE INTO user (username, password, role) VALUES
('admin', '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'admin');

-- 收藏表
CREATE TABLE IF NOT EXISTS favorite (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_product (user_id, product_id)
);

-- AI 对话历史表
CREATE TABLE IF NOT EXISTS ai_chat_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    conversation_id VARCHAR(50),
    role VARCHAR(20) NOT NULL,
    content TEXT,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 用户反馈表（消息级）
-- reply_hash：AI 回复内容的 SHA-256，用作"这条 AI 消息"的稳定身份。
-- 为什么不用消息下标？—— 前端刷新/加载历史后下标会变，会把不同消息的反馈串到一起。
CREATE TABLE IF NOT EXISTS ai_feedback (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    conversation_id VARCHAR(50),
    reply_hash VARCHAR(64) NOT NULL DEFAULT '' COMMENT 'ai_reply 的 SHA-256，消息级去重键',
    user_message TEXT COMMENT '用户当时的提问',
    ai_reply TEXT COMMENT 'AI 的回复',
    feedback VARCHAR(10) NOT NULL COMMENT 'like 或 dislike',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_conv (user_id, conversation_id),
    UNIQUE KEY uk_user_conv_reply (user_id, conversation_id, reply_hash)
);

-- 反馈-商品关联表（反馈归因到具体商品）
-- 一条反馈涉及 N 个被推荐商品 → N 行。范式化的唯一目的：
-- 让"按商品聚合好评率"变成一条能走索引的 GROUP BY，
-- 而不是在 ai_feedback 里存逗号串再用 FIND_IN_SET 全表扫。
CREATE TABLE IF NOT EXISTS ai_feedback_item (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    feedback_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    feedback VARCHAR(10) NOT NULL COMMENT 'like 或 dislike，冗余一份避免聚合时 JOIN',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_product (product_id),
    INDEX idx_feedback_id (feedback_id)
);
