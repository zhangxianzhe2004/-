"""全局配置管理模块

通过环境变量 / .env 文件加载配置，集中管理所有外部依赖（MySQL / Redis / MinIO / Milvus / 模型）的连接参数。
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """系统全局配置项"""

    # ---------- 应用配置 ----------
    APP_NAME: str = "超市商品多模态检索系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    API_PREFIX: str = "/api"

    # ---------- 轻量模式开关 ----------
    # 开启后：MySQL→SQLite、MinIO→本地磁盘、Redis→内存字典、Celery→同步执行、Milvus→内存向量
    # 便于无中间件环境一键启动演示
    LIGHTWEIGHT: bool = True
    # SQLite 数据库文件路径（轻量模式）
    SQLITE_PATH: str = "./data/goods_search.db"
    # 本地图片存储根目录（轻量模式替代 MinIO）
    LOCAL_STORAGE_DIR: str = "./data/storage"

    # ---------- MySQL 配置 ----------
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "123456"
    MYSQL_DATABASE: str = "goods_search"

    # ---------- Redis 配置 ----------
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    # ---------- Celery 配置 ----------
    CELERY_BROKER: str = "redis://127.0.0.1:6379/1"
    CELERY_BACKEND: str = "redis://127.0.0.1:6379/2"

    # ---------- MinIO 对象存储 ----------
    MINIO_ENDPOINT: str = "127.0.0.1:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "goods-images"
    MINIO_SECURE: bool = False

    # ---------- Milvus 向量库 ----------
    # Milvus-Lite 本地模式，使用本地文件存储，无需启动独立服务
    MILVUS_URI: str = "./data/milvus_lite.db"
    MILVUS_COLLECTION_IMAGE: str = "image_vectors"   # 图像向量集合
    MILVUS_COLLECTION_TEXT: str = "text_vectors"     # 文本向量集合
    MILVUS_DIM: int = 512                            # CLIP 图像向量维度
    MILVUS_TEXT_DIM: int = 512                       # BGE 文本向量维度（投影后）
    MILVUS_INDEX_TYPE: str = "IVF_FLAT"
    MILVUS_METRIC_TYPE: str = "COSINE"

    # ---------- 模型配置 ----------
    # 图像向量模型：CLIP（中文 CLIP）
    CLIP_MODEL_NAME: str = "OFA-Sys/chinese-clip-vit-base-patch16"
    # 文本向量模型：BGE 中文
    BGE_MODEL_NAME: str = "BAAI/bge-small-zh-v1.5"
    MODEL_DEVICE: str = "cpu"                         # 本地测试用 cpu，有 GPU 可改 cuda

    # ---------- 检索参数 ----------
    SEARCH_TOP_N: int = 10                            # 默认返回 TopN
    SEARCH_THRESHOLD: float = 0.5                      # 默认相似度阈值
    HYBRID_IMAGE_WEIGHT: float = 0.6                  # 混合检索图像权重
    HYBRID_TEXT_WEIGHT: float = 0.4                   # 混合检索文本权重

    # ---------- 鉴权配置 ----------
    JWT_SECRET_KEY: str = "goods-search-secret-key-please-change-in-prod"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440                    # 24 小时

    # ---------- 导入任务配置 ----------
    IMPORT_BATCH_SIZE: int = 200                      # 单批处理条数
    IMPORT_IMAGE_ZIP_TMP: str = "./data/tmp_import"  # 导入临时目录
    IMPORT_REPORT_DIR: str = "./data/reports"         # 导入报告目录
    IMAGE_THUMBNAIL_SIZE: tuple = (200, 200)          # 缩略图尺寸

    @property
    def MYSQL_URL(self) -> str:
        """MySQL SQLAlchemy 连接串"""
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
        )

    @property
    def DB_URL(self) -> str:
        """当前数据库连接串：轻量模式用 SQLite，否则 MySQL"""
        if self.LIGHTWEIGHT:
            import os
            db_dir = os.path.dirname(self.SQLITE_PATH) or "."
            os.makedirs(db_dir, exist_ok=True)
            return f"sqlite:///{self.SQLITE_PATH}"
        return self.MYSQL_URL

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    """单例获取配置（缓存，避免重复读取 .env）"""
    return Settings()


settings = get_settings()
