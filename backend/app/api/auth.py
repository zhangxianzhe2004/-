"""鉴权 API 路由

提供：登录获取 JWT、获取当前用户信息
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.token import Token
from app.schemas.user import LoginRequest, UserOut
from app.utils.security import verify_password, create_access_token

router = APIRouter()


@router.post("/login", response_model=Token, summary="用户登录")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """用户名密码登录，返回 JWT Token"""
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户已被禁用")
    token = create_access_token(data={"sub": user.username, "role": user.role})
    return Token(access_token=token, role=user.role, username=user.username)


@router.get("/me", response_model=UserOut, summary="获取当前用户")
def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return current_user
