"""JWT Token 相关 Pydantic 模型"""

from pydantic import BaseModel


class Token(BaseModel):
    """登录返回的 Token"""
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class TokenData(BaseModel):
    """Token 解析后的数据"""
    username: str | None = None
