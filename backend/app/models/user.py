"""系统用户表 ORM 模型"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, BigInteger
from sqlalchemy import Integer as SQLInteger
from app.database import Base


class User(Base):
    """系统用户表：简易权限模型（staff/operator/admin）"""

    __tablename__ = "sys_user"

    # SQLite 需要 INTEGER PRIMARY KEY 才能自增，MySQL 用 BigInteger
    user_id = Column(BigInteger().with_variant(SQLInteger, "sqlite"), primary_key=True, autoincrement=True, comment="用户ID")
    username = Column(String(64), unique=True, nullable=False, comment="用户名")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    role = Column(String(16), nullable=False, default="staff", comment="角色")
    is_active = Column(Integer, default=1, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
