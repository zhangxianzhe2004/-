"""密码哈希工具（直接使用 bcrypt，兼容 bcrypt 4.x）"""

import bcrypt


def hash_password(password: str) -> str:
    """生成密码哈希"""
    # bcrypt 限制 72 字节，截断处理
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验密码"""
    pwd_bytes = plain.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(pwd_bytes, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(data: dict) -> str:
    """创建 JWT Token"""
    from datetime import datetime, timedelta
    from jose import jwt
    from app.config import settings
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
