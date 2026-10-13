"""多模态检索相关 Pydantic 模型"""

from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class SearchResultItem(BaseModel):
    """单条检索结果"""
    barcode: str
    goods_name: str
    category: str
    spec: str
    retail_price: Decimal
    shelf_no: Optional[str] = None
    stock: Optional[int] = None
    image_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    score: float = Field(..., description="相似度分数 0~1，越高越相似")


class SearchResponse(BaseModel):
    """检索响应"""
    search_type: str = Field(..., description="检索类型：image/text/barcode/hybrid")
    total: int = Field(0, description="返回结果数")
    cost_ms: int = Field(0, description="检索耗时（毫秒）")
    threshold: float = Field(0.0, description="本次相似度阈值")
    items: list[SearchResultItem] = []


class TextSearchRequest(BaseModel):
    """文本检索请求"""
    query: str = Field(..., description="文本描述，如：红色瓶装可乐")
    top_n: int = Field(10, description="返回 TopN")
    threshold: float = Field(0.5, description="相似度阈值")


class HybridSearchRequest(BaseModel):
    """混合检索请求（图文同时输入）"""
    text_query: Optional[str] = Field(None, description="文本描述")
    top_n: int = 10
    threshold: float = 0.5
    image_weight: float = 0.6
    text_weight: float = 0.4
