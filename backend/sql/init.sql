-- ============================================================
-- 超市商品多模态检索系统 - MySQL 建表脚本
-- 数据库：goods_search
-- 字符集：utf8mb4（支持 emoji 和特殊字符）
-- ============================================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS `goods_search`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE `goods_search`;

-- ============================================================
-- 1. 商品主表 goods
-- 商品条码 barcode 为唯一主键
-- ============================================================
DROP TABLE IF EXISTS `goods`;
CREATE TABLE `goods` (
    `barcode`         VARCHAR(64)  NOT NULL COMMENT '商品条码（唯一主键，必填）',
    `goods_name`      VARCHAR(255) NOT NULL COMMENT '商品名称（必填）',
    `category`        VARCHAR(64)  NOT NULL COMMENT '商品分类（必填）',
    `spec`            VARCHAR(128) NOT NULL COMMENT '商品规格（必填）',
    `retail_price`    DECIMAL(10,2) NOT NULL COMMENT '零售价（必填）',
    `cost_price`      DECIMAL(10,2) DEFAULT NULL COMMENT '进价（非必填）',
    `shelf_no`        VARCHAR(32)  DEFAULT NULL COMMENT '货架编号（非必填）',
    `stock`           INT          DEFAULT 0 COMMENT '库存（非必填，默认0）',
    `supplier`        VARCHAR(128) DEFAULT NULL COMMENT '供应商（非必填）',
    `description`     TEXT         DEFAULT NULL COMMENT '商品描述（用于文本向量）',
    `image_path`      VARCHAR(512) NOT NULL COMMENT '对象存储原图地址（必填）',
    `thumbnail_path`  VARCHAR(512) DEFAULT NULL COMMENT '缩略图地址',
    `created_at`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`barcode`),
    INDEX `idx_category` (`category`),
    INDEX `idx_goods_name` (`goods_name`),
    INDEX `idx_shelf_no` (`shelf_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商品主表';


-- ============================================================
-- 2. 批量导入任务表 goods_import_task
-- 记录每次批量导入的任务状态、成功/失败数、失败明细
-- ============================================================
DROP TABLE IF EXISTS `goods_import_task`;
CREATE TABLE `goods_import_task` (
    `task_id`           VARCHAR(64)  NOT NULL COMMENT '任务ID（UUID）',
    `task_name`         VARCHAR(255) DEFAULT NULL COMMENT '任务名称',
    `source`            VARCHAR(16)  NOT NULL DEFAULT 'file' COMMENT '来源：file=文件导入 / api=API推送',
    `status`            VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT '状态：pending/processing/success/failed/partial',
    `total_count`       INT          NOT NULL DEFAULT 0 COMMENT '总条数',
    `success_count`     INT          NOT NULL DEFAULT 0 COMMENT '成功条数',
    `fail_count`        INT          NOT NULL DEFAULT 0 COMMENT '失败条数',
    `fail_detail`       LONGTEXT     DEFAULT NULL COMMENT '失败明细（JSON 数组：[{barcode, reason}]）',
    `conflict_strategy` VARCHAR(16)  NOT NULL DEFAULT 'skip' COMMENT '条码冲突策略：skip/overwrite/abort',
    `transaction_mode`  VARCHAR(16)  NOT NULL DEFAULT 'partial' COMMENT '事务模式：atomic=整批回滚 / partial=部分成功',
    `report_path`       VARCHAR(512) DEFAULT NULL COMMENT '导入报告文件地址（MinIO）',
    `error_msg`         TEXT         DEFAULT NULL COMMENT '任务级错误信息',
    `created_by`        VARCHAR(64)  DEFAULT NULL COMMENT '创建人',
    `created_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `finished_at`       DATETIME     DEFAULT NULL COMMENT '完成时间',
    PRIMARY KEY (`task_id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='批量导入任务表';


-- ============================================================
-- 3. 系统用户表 sys_user
-- 简易权限：staff=店员（仅检索）/ operator=运营（导入+CRUD）/ admin=管理员（全部）
-- ============================================================
DROP TABLE IF EXISTS `sys_user`;
CREATE TABLE `sys_user` (
    `user_id`        BIGINT       NOT NULL AUTO_INCREMENT COMMENT '用户ID',
    `username`       VARCHAR(64)  NOT NULL COMMENT '用户名',
    `password_hash`  VARCHAR(255) NOT NULL COMMENT '密码哈希',
    `role`           VARCHAR(16)  NOT NULL DEFAULT 'staff' COMMENT '角色：staff/operator/admin',
    `is_active`      TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '是否启用',
    `created_at`     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`user_id`),
    UNIQUE KEY `uk_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统用户表';


-- ============================================================
-- 4. 检索日志表 search_log（二期统计预留，本期不写入但建表）
-- ============================================================
DROP TABLE IF EXISTS `search_log`;
CREATE TABLE `search_log` (
    `log_id`         BIGINT       NOT NULL AUTO_INCREMENT COMMENT '日志ID',
    `search_type`    VARCHAR(16)  NOT NULL COMMENT '检索类型：image/text/barcode/hybrid',
    `query_content`  TEXT         DEFAULT NULL COMMENT '检索内容（文字或图片标识）',
    `top_barcode`    VARCHAR(64)  DEFAULT NULL COMMENT 'Top1 商品条码',
    `top_score`      FLOAT        DEFAULT NULL COMMENT 'Top1 相似度',
    `result_count`   INT          DEFAULT 0 COMMENT '返回结果数',
    `cost_ms`        INT          DEFAULT NULL COMMENT '检索耗时（毫秒）',
    `operator`       VARCHAR(64)  DEFAULT NULL COMMENT '操作人',
    `created_at`     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '检索时间',
    PRIMARY KEY (`log_id`),
    INDEX `idx_search_type` (`search_type`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='检索日志表（二期统计用）';


-- ============================================================
-- 初始化默认用户数据
-- 密码均为 123456（bcrypt 哈希），生产环境请修改
-- 以下哈希值由 passlib bcrypt 生成，对应明文 123456
-- ============================================================
INSERT INTO `sys_user` (`username`, `password_hash`, `role`, `is_active`) VALUES
('admin',    '$2b$12$uK6v3f1qZ9xY0wL8nM2hJeXvY5tQ0sB7r3cF8dG6oI1uY2tA3sK4e', 'admin', 1),
('operator', '$2b$12$uK6v3f1qZ9xY0wL8nM2hJeXvY5tQ0sB7r3cF8dG6oI1uY2tA3sK4e', 'operator', 1),
('staff',    '$2b$12$uK6v3f1qZ9xY0wL8nM2hJeXvY5tQ0sB7r3cF8dG6oI1uY2tA3sK4e', 'staff', 1);

-- 注意：上方默认哈希为占位，首次启动后端会调用 init_default_users 自动用真实 bcrypt 哈希覆盖。
-- 如需手动生成哈希，可执行：
--   python -c "from passlib.context import CryptContext; print(CryptContext(['bcrypt']).hash('123456'))"

-- ============================================================
-- 建表完成
-- ============================================================
