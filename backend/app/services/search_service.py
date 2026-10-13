"""多模态检索服务

编排四种检索能力：
1. 条码精确检索（MySQL 快路径）
2. 图片检索（CLIP → Milvus 图像向量）
3. 文本检索（BGE → Milvus 文本向量）
4. 混合检索（图文加权融合）
"""

import time
from typing import Optional

from PIL import Image
from sqlalchemy.orm import Session

from app.config import settings
from app.models.goods import Goods
from app.services import vector_service, cache_service
from app.utils.clip_model import extract_image_vector, extract_text_vector


def _barcode_search(db: Session, barcode: str) -> Optional[Goods]:
    """条码精确检索：先查缓存，再查 MySQL"""
    # 1. 查缓存
    cached = cache_service.get_cached_goods(barcode)
    if cached:
        # 缓存命中，返回 ORM 对象（构造临时对象）
        g = Goods()
        for k, v in cached.items():
            setattr(g, k, v)
        return g
    # 2. 查 MySQL
    goods = db.query(Goods).filter(Goods.barcode == barcode).first()
    if goods:
        # 写入缓存
        cache_service.cache_goods(barcode, {
            "barcode": goods.barcode,
            "goods_name": goods.goods_name,
            "category": goods.category,
            "spec": goods.spec,
            "retail_price": float(goods.retail_price),
            "shelf_no": goods.shelf_no,
            "stock": goods.stock,
            "image_path": goods.image_path,
            "thumbnail_path": goods.thumbnail_path,
        })
    return goods


def _keyword_search(db: Session, query: str, top_n: int = 10) -> list[dict]:
    """关键词检索降级：无向量模型时按名称/描述/分类 MySQL LIKE 匹配

    返回 [{"barcode":..., "score":...}]，score 按命中字段权重粗略打分。
    """
    kw = query.strip()
    if not kw:
        return []
    like = f"%{kw}%"
    goods_list = db.query(Goods).filter(
        (Goods.goods_name.contains(kw)) | (Goods.description.contains(kw)) | (Goods.category.contains(kw))
    ).limit(top_n).all()
    out = []
    for g in goods_list:
        score = 0.9 if kw in (g.goods_name or "") else (0.7 if kw in (g.description or "") else 0.5)
        out.append({"barcode": g.barcode, "score": score})
    return out


def _fetch_goods_by_barcodes(db: Session, barcode_score_list: list[dict]) -> list[dict]:
    """根据 barcode 列表从 MySQL 批量回查商品元信息，并拼接 score"""
    if not barcode_score_list:
        return []
    barcodes = [item["barcode"] for item in barcode_score_list]
    score_map = {item["barcode"]: item["score"] for item in barcode_score_list}
    goods_list = db.query(Goods).filter(Goods.barcode.in_(barcodes)).all()
    # 按分数排序
    result = []
    for g in goods_list:
        result.append({
            "barcode": g.barcode,
            "goods_name": g.goods_name,
            "category": g.category,
            "spec": g.spec,
            "retail_price": float(g.retail_price),
            "shelf_no": g.shelf_no,
            "stock": g.stock,
            "image_path": g.image_path,
            "thumbnail_path": g.thumbnail_path,
            "score": score_map.get(g.barcode, 0.0),
        })
    result.sort(key=lambda x: x["score"], reverse=True)
    return result


def search_by_barcode(db: Session, barcode: str) -> dict:
    """条码精确检索

    Returns:
        检索响应字典
    """
    start = time.time()
    goods = _barcode_search(db, barcode.strip())
    cost_ms = int((time.time() - start) * 1000)
    if goods is None:
        return {
            "search_type": "barcode",
            "total": 0,
            "cost_ms": cost_ms,
            "threshold": 1.0,
            "items": [],
        }
    return {
        "search_type": "barcode",
        "total": 1,
        "cost_ms": cost_ms,
        "threshold": 1.0,
        "items": [{
            "barcode": goods.barcode,
            "goods_name": goods.goods_name,
            "category": goods.category,
            "spec": goods.spec,
            "retail_price": float(goods.retail_price),
            "shelf_no": goods.shelf_no,
            "stock": goods.stock,
            "image_path": goods.image_path,
            "thumbnail_path": goods.thumbnail_path,
            "score": 1.0,
        }],
    }


def search_by_image(db: Session, image: Image.Image, top_n: int = 10, threshold: float = None) -> dict:
    """图片检索

    Args:
        db: 数据库会话
        image: PIL 图片
        top_n: 返回 TopN
        threshold: 相似度阈值，低于此值不返回
    """
    if threshold is None:
        threshold = settings.SEARCH_THRESHOLD
    start = time.time()
    # 1. CLIP 提取图像向量
    query_vector = extract_image_vector(image)
    # 2. Milvus 检索 TopN
    hits = vector_service.search_image_vectors(query_vector, top_n=top_n)
    # 3. 阈值过滤
    hits = [h for h in hits if h["score"] >= threshold]
    # 4. MySQL 回查元信息
    items = _fetch_goods_by_barcodes(db, hits)
    cost_ms = int((time.time() - start) * 1000)
    return {
        "search_type": "image",
        "total": len(items),
        "cost_ms": cost_ms,
        "threshold": threshold,
        "items": items,
    }


def search_by_text(db: Session, query: str, top_n: int = 10, threshold: float = None) -> dict:
    """文本检索

    Args:
        query: 文本描述，如"红色瓶装可乐"
        top_n: 返回 TopN
        threshold: 相似度阈值
    """
    if threshold is None:
        threshold = settings.SEARCH_THRESHOLD
    start = time.time()
    # 1. BGE 提取文本向量
    query_vector = extract_text_vector(query)
    # 2. 向量检索
    hits = vector_service.search_text_vectors(query_vector, top_n=top_n)
    # 3. 阈值过滤
    hits = [h for h in hits if h["score"] >= threshold]
    # 4. 降级：向量全零（模型未加载）时走关键词检索
    if not hits and all(abs(v) < 1e-9 for v in query_vector):
        hits = _keyword_search(db, query, top_n=top_n)
    # 5. MySQL 回查
    items = _fetch_goods_by_barcodes(db, hits)
    cost_ms = int((time.time() - start) * 1000)
    return {
        "search_type": "text",
        "total": len(items),
        "cost_ms": cost_ms,
        "threshold": threshold,
        "items": items,
    }


def search_hybrid(
    db: Session,
    image: Optional[Image.Image] = None,
    text_query: Optional[str] = None,
    top_n: int = 10,
    threshold: float = None,
    image_weight: float = None,
    text_weight: float = None,
) -> dict:
    """混合检索：图文同时输入，加权融合结果

    融合策略：
    - 图像检索 TopN + 文本检索 TopN
    - 按 barcode 归并，加权打分
    - 最终排序取 TopN
    """
    if threshold is None:
        threshold = settings.SEARCH_THRESHOLD
    if image_weight is None:
        image_weight = settings.HYBRID_IMAGE_WEIGHT
    if text_weight is None:
        text_weight = settings.HYBRID_TEXT_WEIGHT

    start = time.time()
    img_hits = []
    text_hits = []
    # 扩大召回量，融合后再取 TopN
    recall_n = top_n * 3
    img_vector_zero = False
    if image is not None:
        img_vector = extract_image_vector(image)
        img_hits = vector_service.search_image_vectors(img_vector, top_n=recall_n)
        img_vector_zero = all(abs(v) < 1e-9 for v in img_vector)
    text_vector_zero = False
    if text_query:
        text_vector = extract_text_vector(text_query)
        text_hits = vector_service.search_text_vectors(text_vector, top_n=recall_n)
        text_vector_zero = all(abs(v) < 1e-9 for v in text_vector)
    # 降级：文本向量全零（模型未加载）时走关键词检索
    if text_query and not text_hits and text_vector_zero:
        text_hits = _keyword_search(db, text_query, top_n=recall_n)

    # 加权融合：按 barcode 聚合
    score_map: dict[str, float] = {}
    # 归一化权重（图像/文本可能只传其一）
    total_w = (image_weight if image is not None else 0) + (text_weight if text_query else 0)
    if total_w <= 0:
        total_w = 1.0
    w_img = (image_weight if image is not None else 0) / total_w
    w_txt = (text_weight if text_query else 0) / total_w

    for h in img_hits:
        bc = h["barcode"]
        score_map[bc] = score_map.get(bc, 0.0) + h["score"] * w_img
    for h in text_hits:
        bc = h["barcode"]
        score_map[bc] = score_map.get(bc, 0.0) + h["score"] * w_txt

    # 阈值过滤 + 排序
    filtered = [{"barcode": bc, "score": s} for bc, s in score_map.items() if s >= threshold]
    filtered.sort(key=lambda x: x["score"], reverse=True)
    filtered = filtered[:top_n]

    items = _fetch_goods_by_barcodes(db, filtered)
    cost_ms = int((time.time() - start) * 1000)
    return {
        "search_type": "hybrid",
        "total": len(items),
        "cost_ms": cost_ms,
        "threshold": threshold,
        "items": items,
    }
