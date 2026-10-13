"""超市商品多模态检索系统 - FastAPI 主入口

启动时：
1. 初始化数据库表（若不存在）
2. 初始化默认用户
3. 初始化向量库集合
4. 注册路由、CORS、静态文件
5. 轻量模式提供本地图片文件服务端点
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import settings
from app.database import Base, engine, SessionLocal
from app.api import api_router
from app.models.user import User
from app.utils.security import hash_password


def init_db():
    """初始化数据库表（若不存在则创建）"""
    Base.metadata.create_all(bind=engine)


def init_default_users():
    """初始化默认用户（admin/operator/staff，密码 123456）"""
    db = SessionLocal()
    try:
        default_users = [
            ("admin", "admin", "admin"),
            ("operator", "operator", "operator"),
            ("staff", "staff", "staff"),
        ]
        for username, password, role in default_users:
            if not db.query(User).filter(User.username == username).first():
                db.add(User(
                    username=username,
                    password_hash=hash_password(password),
                    role=role,
                    is_active=1,
                ))
        db.commit()
    finally:
        db.close()


def init_milvus():
    """初始化向量库（Milvus 或内存降级）"""
    try:
        from app.services import vector_service
        vector_service._try_init_milvus()
        print("[启动] 向量库初始化完成")
    except Exception as e:
        print(f"[警告] 向量库初始化异常（已降级内存）：{e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化"""
    print("=" * 50)
    print(f"  {settings.APP_NAME} v{settings.APP_VERSION} 启动中...")
    print(f"  模式：{'轻量模式（SQLite+本地存储+内存缓存）' if settings.LIGHTWEIGHT else '完整模式（MySQL+MinIO+Redis）'}")
    print("=" * 50)
    # 初始化数据库
    init_db()
    print("[启动] 数据库表初始化完成")
    # 初始化默认用户
    init_default_users()
    print("[启动] 默认用户初始化完成（admin/operator/staff，密码 123456）")
    # 初始化向量库
    init_milvus()
    # 初始化 MinIO bucket（仅完整模式）
    if not settings.LIGHTWEIGHT:
        try:
            from app.services import storage_service
            storage_service.get_minio_client()
            print("[启动] MinIO 连接完成")
        except Exception as e:
            print(f"[警告] MinIO 连接失败：{e}")
    else:
        # 轻量模式：确保本地存储目录存在
        os.makedirs(settings.LOCAL_STORAGE_DIR, exist_ok=True)
        os.makedirs(os.path.join(settings.LOCAL_STORAGE_DIR, "images"), exist_ok=True)
        os.makedirs(os.path.join(settings.LOCAL_STORAGE_DIR, "thumbnails"), exist_ok=True)
        os.makedirs(os.path.join(settings.LOCAL_STORAGE_DIR, "reports"), exist_ok=True)
        print(f"[启动] 本地存储目录就绪：{settings.LOCAL_STORAGE_DIR}")
    yield
    print("应用关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="超市商品多模态检索系统 - 图片/文字/条码多模态检索 + 批量导入",
    lifespan=lifespan,
)

# CORS：允许前端跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/", summary="健康检查")
def health():
    """根路径健康检查"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "lightweight": settings.LIGHTWEIGHT,
        "docs": "/docs",
    }


@app.get("/api/file/{filepath:path}", summary="本地图片文件服务（轻量模式）")
def serve_local_file(filepath: str):
    """提供本地存储图片的访问端点（轻量模式替代 MinIO）"""
    if not settings.LIGHTWEIGHT:
        raise HTTPException(status_code=404, detail="仅轻量模式提供本地文件服务")
    full_path = os.path.join(settings.LOCAL_STORAGE_DIR, filepath)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    # 安全检查：防止路径穿越
    real_path = os.path.realpath(full_path)
    if not real_path.startswith(os.path.realpath(settings.LOCAL_STORAGE_DIR)):
        raise HTTPException(status_code=403, detail="禁止访问")
    return FileResponse(real_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
