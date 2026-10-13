"""用户相关 Pydantic 模型"""

from pydantic import BaseModel


class UserBase(BaseModel):
    username: str
    role: str = "staff"


class UserOut(UserBase):
    """用户信息输出"""
    user_id: int
    is_active: int

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str
