"""商品相关 Pydantic 模型"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class GoodsBase(BaseModel):
    """商品基础字段"""
    goods_name: str = Field(..., description="商品名称")
    category: str = Field(..., description="商品分类")
    spec: str = Field(..., description="商品规格")
    retail_price: Decimal = Field(..., description="零售价")
    cost_price: Optional[Decimal] = None
    shelf_no: Optional[str] = None
    stock: Optional[int] = 0
    supplier: Optional[str] = None
    description: Optional[str] = None


class GoodsCreate(GoodsBase):
    """创建商品"""
    barcode: str = Field(..., description="商品条码")
    image_path: str = Field(..., description="对象存储图片地址")


class GoodsUpdate(BaseModel):
    """编辑商品（所有字段可选）"""
    goods_name: Optional[str] = None
    category: Optional[str] = None
    spec: Optional[str] = None
    retail_price: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    shelf_no: Optional[str] = None
    stock: Optional[int] = None
    supplier: Optional[str] = None
    description: Optional[str] = None
    image_path: Optional[str] = None


class GoodsOut(GoodsBase):
    """商品输出"""
    barcode: str
    image_path: str
    thumbnail_path: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GoodsListOut(BaseModel):
    """商品列表分页输出"""
    total: int
    page: int
    page_size: int
    items: list[GoodsOut]


# ============================================================
# 批量导入 API 推送（方案B）：单条商品 + base64 图片
# ============================================================
class GoodsPushItem(GoodsBase):
    """API 批量推送的单条商品（方案B）"""
    barcode: str = Field(..., description="商品条码")
    image_base64: str = Field(..., description="商品图片 base64 编码（不含 data:image 前缀）")


class GoodsPushRequest(BaseModel):
    """API 批量推送请求体"""
    items: list[GoodsPushItem]
    conflict_strategy: str = Field("skip", description="冲突策略：skip/overwrite/abort")
    transaction_mode: str = Field("partial", description="事务模式：atomic/partial")
