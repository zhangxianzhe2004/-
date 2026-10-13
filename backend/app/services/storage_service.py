"""对象存储服务

负责商品原图和缩略图的上传、下载、删除。
轻量模式：存储到本地磁盘（LOCAL_STORAGE_DIR），无需 MinIO。
完整模式：存储到 MinIO。
"""

import io
import os
from typing import Optional

from app.config import settings

_client = None  # MinIO 客户端单例（完整模式）


def get_minio_client():
    """获取 MinIO 客户端单例（完整模式）"""
    global _client
    if _client is None:
        from minio import Minio
        from minio.error import S3Error
        _client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        _ensure_bucket(_client, settings.MINIO_BUCKET)
    return _client


def _ensure_bucket(client, bucket: str):
    """确保 bucket 存在，不存在则创建"""
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
    except Exception as e:
        print(f"[警告] MinIO bucket 创建失败：{e}")


# ============ 本地存储（轻量模式） ============

def _local_full_path(object_name: str) -> str:
    """本地存储完整路径"""
    return os.path.join(settings.LOCAL_STORAGE_DIR, object_name)


def _local_upload(object_name: str, data: bytes) -> str:
    """本地写入文件"""
    full_path = _local_full_path(object_name)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as f:
        f.write(data)
    # 返回相对路径（供 /api/file 访问）
    return object_name


def _local_download(object_name: str) -> bytes:
    """本地读取文件"""
    full_path = _local_full_path(object_name)
    with open(full_path, "rb") as f:
        return f.read()


def _local_delete(object_name: str):
    """本地删除文件"""
    full_path = _local_full_path(object_name)
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
    except Exception as e:
        print(f"[警告] 删除本地文件失败：{e}")


def _strip_bucket(object_path: str) -> str:
    """去除 bucket 前缀，返回纯 object_name"""
    if object_path.startswith(f"{settings.MINIO_BUCKET}/"):
        return object_path[len(settings.MINIO_BUCKET) + 1:]
    return object_path


# ============ 统一对外接口 ============

def upload_image(object_name: str, img_bytes: bytes, content_type: str = "image/jpeg") -> str:
    """上传图片

    Args:
        object_name: 对象存储中的路径，如 images/6901234567890.jpg
        img_bytes: 图片字节
        content_type: MIME 类型
    Returns:
        轻量模式返回 object_name；完整模式返回 bucket/object_name
    """
    if settings.LIGHTWEIGHT:
        return _local_upload(object_name, img_bytes)
    # MinIO 模式
    client = get_minio_client()
    client.put_object(
        settings.MINIO_BUCKET,
        object_name,
        io.BytesIO(img_bytes),
        length=len(img_bytes),
        content_type=content_type,
    )
    return f"{settings.MINIO_BUCKET}/{object_name}"


def upload_goods_image(barcode: str, img_bytes: bytes, is_thumbnail: bool = False) -> str:
    """上传商品图片，按 barcode 组织路径

    Args:
        barcode: 商品条码
        img_bytes: 图片字节
        is_thumbnail: 是否为缩略图
    Returns:
        对象存储路径标识
    """
    prefix = "thumbnails" if is_thumbnail else "images"
    object_name = f"{prefix}/{barcode}.jpg"
    return upload_image(object_name, img_bytes)


def get_image_url(object_path: str) -> str:
    """根据对象存储路径生成可访问的 URL

    轻量模式：返回 /api/file/{object_name}，由后端静态服务
    完整模式：返回 MinIO http URL
    """
    if not object_path:
        return ""
    object_name = _strip_bucket(object_path)
    if settings.LIGHTWEIGHT:
        return f"/api/file/{object_name}"
    scheme = "https" if settings.MINIO_SECURE else "http"
    return f"{scheme}://{settings.MINIO_ENDPOINT}/{settings.MINIO_BUCKET}/{object_name}"


def download_file(object_path: str) -> bytes:
    """下载对象存储中的文件"""
    object_name = _strip_bucket(object_path)
    if settings.LIGHTWEIGHT:
        return _local_download(object_name)
    client = get_minio_client()
    response = client.get_object(settings.MINIO_BUCKET, object_name)
    return response.read()


def delete_image(object_path: str):
    """删除对象存储中的图片"""
    if not object_path:
        return
    object_name = _strip_bucket(object_path)
    if settings.LIGHTWEIGHT:
        _local_delete(object_name)
        return
    try:
        from minio.error import S3Error
        client = get_minio_client()
        client.remove_object(settings.MINIO_BUCKET, object_name)
    except Exception as e:
        print(f"[警告] 删除对象失败：{e}")
