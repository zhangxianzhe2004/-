"""批量商品导入服务（最高优先级）

核心流程：
1. 接收 Excel/CSV + 图片压缩包（或 API JSON）
2. 解析 → 字段校验 → 条码查重 → 冲突策略判定
3. 异步任务：图片处理 → 上传 MinIO → 写 MySQL → 写 Milvus 向量
4. 事务模式：atomic（整批回滚）/ partial（失败导出）
5. 生成导入报告

本模块只负责"数据准备 + 单条写入逻辑"，大批量异步编排由 Celery 任务完成。
"""

import os
import json
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.goods import Goods
from app.models.import_task import ImportTask
from app.services import storage_service, vector_service, cache_service
from app.utils.clip_model import extract_image_vector, extract_text_vector
from app.utils.image_utils import bytes_to_image, make_thumbnail, image_to_bytes

import io
from PIL import Image


def create_task(
    db: Session,
    task_name: str,
    source: str,
    total_count: int,
    conflict_strategy: str,
    transaction_mode: str,
    created_by: str,
) -> ImportTask:
    """创建导入任务记录，返回任务对象"""
    task = ImportTask(
        task_id=str(uuid.uuid4().hex),
        task_name=task_name,
        source=source,
        status="pending",
        total_count=total_count,
        success_count=0,
        fail_count=0,
        fail_detail="[]",
        conflict_strategy=conflict_strategy,
        transaction_mode=transaction_mode,
        created_by=created_by,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def process_single_goods(
    db: Session,
    record: dict,
    image_bytes: Optional[bytes],
    conflict_strategy: str,
) -> tuple[bool, str]:
    """处理单条商品入库（含图片上传 + 向量写入）

    用于 partial 模式：每条独立事务，失败不影响其他条目。
    Args:
        record: 商品字段字典
        image_bytes: 图片字节（可为空，仅 API 推送时可能缺图）
        conflict_strategy: 冲突策略 skip/overwrite
    Returns:
        (success, message)
    """
    barcode = record["barcode"]
    # 1. 条码查重
    existing = db.query(Goods).filter(Goods.barcode == barcode).first()
    if existing:
        if conflict_strategy == "skip":
            return False, f"条码 {barcode} 已存在，跳过"
        elif conflict_strategy == "overwrite":
            # 覆盖：删除旧数据（含 MinIO 图片 + Milvus 向量）
            storage_service.delete_image(existing.image_path)
            storage_service.delete_image(existing.thumbnail_path or "")
            vector_service.delete_barcode_vectors(barcode)
            db.delete(existing)
            db.flush()
        else:
            return False, f"条码 {barcode} 已存在，策略为 abort 终止"
    # 2. 图片处理 + 上传 MinIO
    image_path = ""
    thumbnail_path = ""
    if image_bytes:
        img = bytes_to_image(image_bytes)
        # 上传原图
        image_path = storage_service.upload_goods_image(barcode, image_bytes)
        # 生成并上传缩略图
        thumb = make_thumbnail(img)
        thumb_bytes = image_to_bytes(thumb)
        thumbnail_path = storage_service.upload_goods_image(barcode, thumb_bytes, is_thumbnail=True)
    else:
        # 无图片：使用占位路径
        image_path = f"images/{barcode}.jpg"

    # 3. 写 MySQL
    goods = Goods(
        barcode=barcode,
        goods_name=record["goods_name"],
        category=record["category"],
        spec=record["spec"],
        retail_price=record["retail_price"],
        cost_price=record.get("cost_price"),
        shelf_no=record.get("shelf_no"),
        stock=record.get("stock", 0),
        supplier=record.get("supplier"),
        description=record.get("description"),
        image_path=image_path,
        thumbnail_path=thumbnail_path,
    )
    db.add(goods)
    db.flush()
    return True, "ok"


def generate_vectors_for_goods(record: dict, barcode: str, image_bytes: Optional[bytes]):
    """为商品生成图像向量 + 文本向量并写入 Milvus

    在 MySQL 提交后调用，保证一致性。
    """
    # 图像向量
    if image_bytes:
        img = bytes_to_image(image_bytes)
        img_vector = extract_image_vector(img)
        vector_service.insert_image_vector(barcode, img_vector, record.get("category", ""))
    # 文本向量：商品名称 + 描述拼接
    text_content = record.get("goods_name", "")
    if record.get("description"):
        text_content += " " + record["description"]
    if record.get("category"):
        text_content += " " + record["category"]
    if record.get("spec"):
        text_content += " " + record["spec"]
    text_vector = extract_text_vector(text_content)
    vector_service.insert_text_vector(barcode, text_vector, record.get("category", ""))


def build_report(task: ImportTask) -> bytes:
    """生成导入报告 CSV 内容"""
    import csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["任务ID", task.task_id])
    writer.writerow(["任务名称", task.task_name or ""])
    writer.writerow(["来源", task.source])
    writer.writerow(["状态", task.status])
    writer.writerow(["总条数", task.total_count])
    writer.writerow(["成功条数", task.success_count])
    writer.writerow(["失败条数", task.fail_count])
    writer.writerow(["冲突策略", task.conflict_strategy])
    writer.writerow(["事务模式", task.transaction_mode])
    writer.writerow(["创建时间", str(task.created_at)])
    writer.writerow(["完成时间", str(task.finished_at or "")])
    writer.writerow([])
    writer.writerow(["序号", "条码", "失败原因"])
    fail_list = json.loads(task.fail_detail or "[]")
    for i, item in enumerate(fail_list, 1):
        writer.writerow([i, item.get("barcode", ""), item.get("reason", "")])
    return output.getvalue().encode("utf-8-sig")


def update_task_status(
    task_id: str,
    status: str,
    success_count: int = None,
    fail_count: int = None,
    fail_detail: list = None,
    report_path: str = None,
    error_msg: str = None,
):
    """更新任务状态（在独立会话中操作，避免事务冲突）"""
    db = SessionLocal()
    try:
        task = db.query(ImportTask).filter(ImportTask.task_id == task_id).first()
        if task is None:
            return
        task.status = status
        if success_count is not None:
            task.success_count = success_count
        if fail_count is not None:
            task.fail_count = fail_count
        if fail_detail is not None:
            task.fail_detail = json.dumps(fail_detail, ensure_ascii=False)
        if report_path is not None:
            task.report_path = report_path
        if error_msg is not None:
            task.error_msg = error_msg
        if status in ("success", "failed", "partial"):
            task.finished_at = datetime.now()
        db.commit()
        # 同步更新 Redis 进度缓存
        cache_service.set_task_progress(task_id, {
            "status": status,
            "success_count": task.success_count,
            "fail_count": task.fail_count,
            "total_count": task.total_count,
        })
    finally:
        db.close()


def upload_report(task: ImportTask) -> str:
    """上传导入报告到 MinIO，返回路径"""
    report_bytes = build_report(task)
    object_name = f"reports/{task.task_id}_report.csv"
    path = storage_service.upload_image(object_name, report_bytes, content_type="text/csv")
    return path
