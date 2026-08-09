-- ============================================================
-- 迁移 V2：反馈归因到商品（供推荐排序消费）
--
-- 适用对象：已经跑起来、库里有数据的旧环境。
-- 全新环境不需要执行本文件 —— init.sql / docker-init.sql 已含新结构。
--
-- 执行方式：
--   docker exec -i <mysql容器> mysql -uroot -p<密码> aishoes < migrate-v2-feedback.sql
--
-- 注意：MySQL 8 不支持 ADD COLUMN IF NOT EXISTS，
-- 重复执行第 1 步会报 Duplicate column，属正常，忽略即可。
-- ============================================================

-- 1) ai_feedback 增加消息级去重键
ALTER TABLE ai_feedback
    ADD COLUMN reply_hash VARCHAR(64) NOT NULL DEFAULT ''
    COMMENT 'ai_reply 的 SHA-256，消息级去重键';

-- 2) 回填历史数据的 reply_hash
--    MySQL 的 SHA2(str, 256) 与 Java MessageDigest("SHA-256") 对 UTF-8 字节串结果一致
UPDATE ai_feedback SET reply_hash = SHA2(IFNULL(ai_reply, ''), 256) WHERE reply_hash = '';

-- 3) 去重后再加唯一键（历史数据可能存在同 hash 重复行，先只保留 id 最大的一条）
DELETE f1 FROM ai_feedback f1
JOIN ai_feedback f2
  ON f1.user_id = f2.user_id
 AND f1.conversation_id <=> f2.conversation_id
 AND f1.reply_hash = f2.reply_hash
 AND f1.id < f2.id;

ALTER TABLE ai_feedback
    ADD UNIQUE KEY uk_user_conv_reply (user_id, conversation_id, reply_hash);

-- 4) 新建反馈-商品关联表
CREATE TABLE IF NOT EXISTS ai_feedback_item (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    feedback_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    feedback VARCHAR(10) NOT NULL COMMENT 'like 或 dislike',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_product (product_id),
    INDEX idx_feedback_id (feedback_id)
);

-- 历史反馈无法回填 product_id（当时前端没上报），
-- 只能从本次迁移之后的新反馈开始积累。这是一次性的数据断层，不补。
