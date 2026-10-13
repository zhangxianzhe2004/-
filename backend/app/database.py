"""数据库连接管理模块

管理数据库（SQLAlchemy）会话，提供 get_db 依赖注入。
轻量模式使用 SQLite（无需安装 MySQL），完整模式使用 MySQL。
"""

import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from app.config import settings

if settings.LIGHTWEIGHT:
    # 轻量模式：SQLite，多线程安全关闭检查
    _db_dir = os.path.dirname(settings.SQLITE_PATH) or "."
    os.makedirs(_db_dir, exist_ok=True)
    engine = create_engine(
        settings.DB_URL,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},  # SQLite 多线程兼容
    )

    # SQLite 启用外键约束（默认关闭）
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # 完整模式：MySQL
    engine = create_engine(
        settings.MYSQL_URL,
        pool_pre_ping=True,      # 连接前检测可用性
        pool_recycle=3600,       # 连接回收周期
        pool_size=10,            # 连接池大小
        max_overflow=20,         # 溢出连接数
        echo=settings.DEBUG,     # 调试模式打印 SQL
    )

# 会话工厂
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# ORM 基类
Base = declarative_base()


def get_db():
    """FastAPI 依赖注入：获取数据库会话，请求结束自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
