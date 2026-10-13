"""批量导入异步任务

负责异步/同步执行批量商品入库：
- 方案A：文件导入（Excel + 图片 zip）
- 方案B：API 推送（JSON + base64 图片）

任务流程：
1. 更新任务状态为 processing
2. 按事务模式（atomic / partial）处理每条商品
3. 写 MySQL → 生成图像向量 + 文本向量 → 写向量库
4. atomic 模式：任一条失败回滚全部；partial 模式：逐条独立事务
5. 生成导入报告
6. 更新任务状态为 success / partial / failed

Celery 可用时通过 .delay() 异步执行；不可用时同步执行（轻量模式）。
"""

import base64
import json
import threading
from typing import Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.import_task import ImportTask
from app.services import import_service, cache_service, vector_service
from app.utils.image_utils import base64_to_image
from app.tasks.celery_app import celery_app, CELERY_AVAILABLE


def submit_import_file(task_id, records, image_map_base64, conflict_strategy, transaction_mode):
    """提交方案A导入任务：Celery 可用则异步，否则同步（轻量模式）"""
    if CELERY_AVAILABLE and celery_app is not None:
        # 异步：通过 Celery 注册任务
        _registered["process_import_file"].delay(
            task_id=task_id,
            records=records,
            image_map_base64=image_map_base64,
            conflict_strategy=conflict_strategy,
            transaction_mode=transaction_mode,
        )
    else:
        # 同步：后台线程执行，避免阻塞 API 响应
        t = threading.Thread(
            target=_do_import,
            args=(task_id, records, image_map_base64, conflict_strategy, transaction_mode),
            daemon=True,
        )
        t.start()


def submit_import_api(task_id, records, image_map_base64, conflict_strategy, transaction_mode):
    """提交方案B导入任务"""
    if CELERY_AVAILABLE and celery_app is not None:
        _registered["process_import_api"].delay(
            task_id=task_id,
            records=records,
            image_map_base64=image_map_base64,
            conflict_strategy=conflict_strategy,
            transaction_mode=transaction_mode,
        )
    else:
        t = threading.Thread(
            target=_do_import,
            args=(task_id, records, image_map_base64, conflict_strategy, transaction_mode),
            daemon=True,
        )
        t.start()


# Celery 任务注册（仅 Celery 可用时）
_registered = {}
if CELERY_AVAILABLE and celery_app is not None:
    @celery_app.task(name="process_import_file")
    def process_import_file(task_id, records, image_map_base64, conflict_strategy, transaction_mode):
        """方案A：文件导入异步处理"""
        return _do_import(task_id, records, image_map_base64, conflict_strategy, transaction_mode)

    @celery_app.task(name="process_import_api")
    def process_import_api(task_id, records, image_map_base64, conflict_strategy, transaction_mode):
        """方案B：API 批量推送异步处理"""
        return _do_import(task_id, records, image_map_base64, conflict_strategy, transaction_mode)

    _registered = {
        "process_import_file": process_import_file,
        "process_import_api": process_import_api,
    }


def _do_import(
    task_id: str,
    records: list[dict],
    image_map_base64: dict,
    conflict_strategy: str,
    transaction_mode: str,
):
    """批量导入核心处理逻辑（两种方案共用）"""
    db = SessionLocal()
    success_count = 0
    fail_list = []

    try:
        # 更新任务为处理中
        import_service.update_task_status(task_id, "processing")

        # ========== 事务模式分支 ==========
        if transaction_mode == "atomic":
            # 整批原子：单事务，任一失败全部回滚
            try:
                goods_to_vector = []
                for idx, record in enumerate(records):
                    barcode = record["barcode"]
                    img_bytes = _decode_image(image_map_base64.get(barcode))
                    ok, msg = import_service.process_single_goods(db, record, img_bytes, conflict_strategy)
                    if not ok:
                        raise ValueError(f"第{idx + 1}条失败（{barcode}）：{msg}")
                    success_count += 1
                    goods_to_vector.append((record, barcode, img_bytes))
                # 全部成功，提交 MySQL
                db.commit()
                # MySQL 提交成功后才写向量库
                for record, barcode, img_bytes in goods_to_vector:
                    import_service.generate_vectors_for_goods(record, barcode, img_bytes)
                    cache_service.invalidate_goods(barcode)
                status = "success"
            except Exception as e:
                db.rollback()
                success_count = 0
                fail_list = [{"barcode": r["barcode"], "reason": str(e)} for r in records]
                status = "failed"
                import_service.update_task_status(task_id, status, success_count=0,
                                                  fail_count=len(fail_list), fail_detail=fail_list,
                                                  error_msg=str(e))
                _finalize_report(db, task_id, status, success_count, fail_list)
                return {"task_id": task_id, "status": status}
        else:
            # partial 模式：逐条独立事务
            for idx, record in enumerate(records):
                barcode = record["barcode"]
                img_bytes = _decode_image(image_map_base64.get(barcode))
                item_db = SessionLocal()
                try:
                    ok, msg = import_service.process_single_goods(item_db, record, img_bytes, conflict_strategy)
                    item_db.commit()
                    if ok:
                        success_count += 1
                        import_service.generate_vectors_for_goods(record, barcode, img_bytes)
                        cache_service.invalidate_goods(barcode)
                    else:
                        fail_list.append({"barcode": barcode, "reason": msg})
                except Exception as e:
                    item_db.rollback()
                    fail_list.append({"barcode": barcode, "reason": f"处理异常：{e}"})
                finally:
                    item_db.close()
            status = "success" if not fail_list else ("partial" if success_count > 0 else "failed")

        # 更新任务状态
        fail_count = len(fail_list)
        import_service.update_task_status(
            task_id, status,
            success_count=success_count,
            fail_count=fail_count,
            fail_detail=fail_list,
        )
        _finalize_report(db, task_id, status, success_count, fail_list)
        return {"task_id": task_id, "status": status, "success": success_count, "fail": fail_count}

    except Exception as e:
        db.rollback()
        import_service.update_task_status(
            task_id, "failed",
            success_count=success_count,
            fail_count=len(records) - success_count,
            fail_detail=fail_list,
            error_msg=str(e),
        )
        return {"task_id": task_id, "status": "failed", "error": str(e)}
    finally:
        db.close()


def _decode_image(b64: Optional[str]):
    """解码 base64 图片为字节"""
    if not b64:
        return None
    try:
        return base64.b64decode(b64)
    except Exception:
        return None


def _finalize_report(db: Session, task_id: str, status: str, success_count: int, fail_list: list):
    """生成并上传导入报告"""
    try:
        task = db.query(ImportTask).filter(ImportTask.task_id == task_id).first()
        if task is None:
            return
        task.status = status
        task.success_count = success_count
        task.fail_count = len(fail_list)
        task.fail_detail = json.dumps(fail_list, ensure_ascii=False)
        report_path = import_service.upload_report(task)
        task.report_path = report_path
        db.commit()
    except Exception as e:
        print(f"[报告生成失败] task={task_id} err={e}")
