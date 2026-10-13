"""多模态检索 API 路由

提供四种检索接口：
1. POST /search/image   图片检索
2. POST /search/text    文本检索
3. GET  /search/barcode/{barcode}  条码精确检索
4. POST /search/hybrid  图文混合检索
5. POST /search/ocr     OCR 检索（二期预留）
"""

import io
from fastapi import APIRouter, Depends, File, Form, UploadFile
from PIL import Image
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.schemas.search import SearchResponse, TextSearchRequest, HybridSearchRequest
from app.services import search_service
from app.utils.image_utils import bytes_to_image

router = APIRouter()


@router.post("/image", response_model=SearchResponse, summary="图片检索")
async def search_image(
    file: UploadFile = File(..., description="商品图片"),
    top_n: int = Form(10),
    threshold: float = Form(0.5),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """上传商品照片，CLIP 提取图像向量，Milvus 召回相似商品"""
    img_bytes = await file.read()
    image = bytes_to_image(img_bytes)
    result = search_service.search_by_image(db, image, top_n=top_n, threshold=threshold)
    return result


@router.post("/text", response_model=SearchResponse, summary="文本检索")
def search_text(
    req: TextSearchRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """输入文字描述（如"红色瓶装可乐"），BGE 文本向量检索"""
    return search_service.search_by_text(db, req.query, top_n=req.top_n, threshold=req.threshold)


@router.get("/barcode/{barcode}", response_model=SearchResponse, summary="条码精确检索")
def search_barcode(
    barcode: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """条码精确检索，MySQL 直查，毫秒级响应"""
    return search_service.search_by_barcode(db, barcode)


@router.post("/hybrid", response_model=SearchResponse, summary="图文混合检索")
async def search_hybrid(
    text_query: str = Form(None, description="文本描述"),
    file: UploadFile = File(None, description="商品图片"),
    top_n: int = Form(10),
    threshold: float = Form(0.5),
    image_weight: float = Form(0.6),
    text_weight: float = Form(0.4),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """图文同时输入，加权融合图像向量 + 文本向量结果"""
    image = None
    if file is not None:
        img_bytes = await file.read()
        image = bytes_to_image(img_bytes)
    return search_service.search_hybrid(
        db, image=image, text_query=text_query, top_n=top_n,
        threshold=threshold, image_weight=image_weight, text_weight=text_weight,
    )


@router.post("/ocr", summary="OCR 检索（二期预留）")
def search_ocr(
    file: UploadFile = File(...),
    _=Depends(get_current_user),
):
    """二期预留：OCR 识别包装文字辅助检索（本期不实现）"""
    return {"message": "OCR 检索为二期功能，接口已预留，暂未实现"}
