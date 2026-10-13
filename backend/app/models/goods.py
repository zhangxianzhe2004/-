"""商品主表 ORM 模型"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, DECIMAL
from app.database import Base


class Goods(Base):
    """商品主表：barcode 为唯一主键"""

    __tablename__ = "goods"

    barcode = Column(String(64), primary_key=True, comment="商品条码")
    goods_name = Column(String(255), nullable=False, comment="商品名称")
    category = Column(String(64), nullable=False, comment="商品分类")
    spec = Column(String(128), nullable=False, comment="商品规格")
    retail_price = Column(DECIMAL(10, 2), nullable=False, comment="零售价")
    cost_price = Column(DECIMAL(10, 2), nullable=True, comment="进价")
    shelf_no = Column(String(32), nullable=True, comment="货架编号")
    stock = Column(Integer, default=0, comment="库存")
    supplier = Column(String(128), nullable=True, comment="供应商")
    description = Column(Text, nullable=True, comment="商品描述")
    image_path = Column(String(512), nullable=False, comment="对象存储原图地址")
    thumbnail_path = Column(String(512), nullable=True, comment="缩略图地址")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
