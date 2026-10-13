"""商品管理 API 路由

提供：商品分页列表、详情、编辑、删除
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_role
from app.models.goods import Goods
from app.models.user import User
from app.schemas.goods import GoodsOut, GoodsListOut, GoodsUpdate
from app.services import cache_service, vector_service, storage_service

router = APIRouter()


@router.get("", response_model=GoodsListOut, summary="商品分页列表")
def list_goods(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None, description="按名称/条码模糊搜索"),
    category: str = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """商品分页列表，支持关键词和分类筛选"""
    q = db.query(Goods)
    if keyword:
        q = q.filter((Goods.goods_name.contains(keyword)) | (Goods.barcode.contains(keyword)))
    if category:
        q = q.filter(Goods.category == category)
    total = q.count()
    items = q.order_by(Goods.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return GoodsListOut(total=total, page=page, page_size=page_size, items=items)


@router.get("/{barcode}", response_model=GoodsOut, summary="商品详情")
def get_goods(barcode: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    goods = db.query(Goods).filter(Goods.barcode == barcode).first()
    if not goods:
        raise HTTPException(status_code=404, detail="商品不存在")
    return goods


@router.put("/{barcode}", response_model=GoodsOut, summary="编辑商品")
def update_goods(
    barcode: str,
    req: GoodsUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_role("operator", "admin")),
):
    goods = db.query(Goods).filter(Goods.barcode == barcode).first()
    if not goods:
        raise HTTPException(status_code=404, detail="商品不存在")
    update_data = req.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(goods, k, v)
    db.commit()
    db.refresh(goods)
    # 失效缓存
    cache_service.invalidate_goods(barcode)
    # 若描述变更，更新文本向量
    if "description" in update_data or "goods_name" in update_data:
        from app.services import import_service
        record = {
            "goods_name": goods.goods_name,
            "category": goods.category,
            "spec": goods.spec,
            "description": goods.description,
        }
        import_service.generate_vectors_for_goods(record, barcode, None)
    return goods


@router.delete("/{barcode}", summary="删除商品")
def delete_goods(
    barcode: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("operator", "admin")),
):
    goods = db.query(Goods).filter(Goods.barcode == barcode).first()
    if not goods:
        raise HTTPException(status_code=404, detail="商品不存在")
    # 删除 MinIO 图片
    storage_service.delete_image(goods.image_path)
    if goods.thumbnail_path:
        storage_service.delete_image(goods.thumbnail_path)
    # 删除 Milvus 向量
    vector_service.delete_barcode_vectors(barcode)
    # 删除 MySQL 记录
    db.delete(goods)
    db.commit()
    cache_service.invalidate_goods(barcode)
    return {"message": f"商品 {barcode} 已删除"}


@router.get("/categories/list", summary="获取所有分类")
def list_categories(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """获取商品分类列表（用于筛选下拉）"""
    cats = db.query(Goods.category).distinct().all()
    return [c[0] for c in cats if c[0]]
