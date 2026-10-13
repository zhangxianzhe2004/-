"""API 路由包"""
from fastapi import APIRouter

from app.api import auth, goods, search, import_task

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["鉴权"])
api_router.include_router(goods.router, prefix="/goods", tags=["商品管理"])
api_router.include_router(search.router, prefix="/search", tags=["多模态检索"])
api_router.include_router(import_task.router, prefix="/import", tags=["批量导入"])
