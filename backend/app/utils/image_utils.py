"""图片处理工具

提供：
- base64 解码为 PIL 图片
- 图片格式校验
- 生成缩略图
- 图片压缩
"""

import base64
import io
from typing import Optional, Tuple

from PIL import Image

from app.config import settings


def base64_to_image(b64_str: str) -> Image.Image:
    """将 base64 字符串解码为 PIL 图片

    支持带 data:image 前缀的格式。
    """
    # 去除 data:image/xxx;base64, 前缀
    if "," in b64_str and b64_str.startswith("data:"):
        b64_str = b64_str.split(",", 1)[1]
    img_data = base64.b64decode(b64_str)
    return Image.open(io.BytesIO(img_data)).convert("RGB")


def bytes_to_image(img_bytes: bytes) -> Image.Image:
    """将字节数据转为 PIL 图片"""
    return Image.open(io.BytesIO(img_bytes)).convert("RGB")


def image_to_bytes(image: Image.Image, fmt: str = "JPEG", quality: int = 85) -> bytes:
    """将 PIL 图片转为字节数据（用于上传 MinIO）"""
    buf = io.BytesIO()
    image.save(buf, format=fmt, quality=quality)
    return buf.getvalue()


def make_thumbnail(image: Image.Image, size: Optional[Tuple[int, int]] = None) -> Image.Image:
    """生成缩略图"""
    if size is None:
        size = settings.IMAGE_THUMBNAIL_SIZE
    thumb = image.copy()
    thumb.thumbnail(size)
    return thumb


def validate_image(img_bytes: bytes) -> bool:
    """校验字节数据是否为有效图片"""
    try:
        Image.open(io.BytesIO(img_bytes)).verify()
        return True
    except Exception:
        return False


def image_to_base64(image: Image.Image, fmt: str = "JPEG") -> str:
    """将 PIL 图片编码为 base64 字符串"""
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")
