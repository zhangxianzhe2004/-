"""批量导入 API 路由

方案A：文件导入 - 上传 Excel/CSV + 图片压缩包
方案B：API 推送 - 接收 JSON 数组（支持 base64 图片）

两种方案均创建异步任务，立即返回 task_id，由 Celery 异步处理。
"""

import base64
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role, get_current_user
from app.models.import_task import ImportTask
from app.models.user import User
from app.schemas.import_task import ImportTaskOut, ImportTaskListOut
from app.schemas.goods import GoodsPushRequest
from app.services import import_service
from app.tasks.import_tasks import submit_import_file, submit_import_api
from app.utils.excel_parser import parse_excel, validate_records, extract_image_names_from_zip
from app.utils.image_utils import image_to_base64, bytes_to_image

router = APIRouter()


@router.post("/upload", response_model=dict, summary="方案A：上传 Excel + 图片zip 批量导入")
async def upload_import(
    excel_file: UploadFile = File(..., description="Excel/CSV 商品清单"),
    image_zip: UploadFile = File(None, description="商品图片压缩包，命名=条码.jpg"),
    conflict_strategy: str = Form("skip", description="冲突策略：skip/overwrite/abort"),
    transaction_mode: str = Form("partial", description="事务模式：atomic/partial"),
    task_name: str = Form(None, description="任务名称"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("operator", "admin")),
):
    """方案A：运营后台上传 Excel/CSV + 图片压缩包

    流程：
    1. 解析 Excel 字段校验
    2. 解压图片 zip，按 barcode 匹配图片
    3. 创建异步任务，立即返回 task_id
    """
    # 1. 解析 Excel
    excel_bytes = await excel_file.read()
    records = parse_excel(excel_bytes, excel_file.filename)
    valid_records, invalid_records = validate_records(records)
    if invalid_records:
        # 校验失败的也记录，后续报告包含
        pass
    if not valid_records:
        raise HTTPException(status_code=400, detail=f"无有效记录，校验失败：{invalid_records[:5]}")

    # 2. 解压图片 zip，按 barcode 匹配
    image_map_base64 = {}
    if image_zip is not None:
        zip_bytes = await image_zip.read()
        img_dict = extract_image_names_from_zip(zip_bytes)
        for barcode, img_bytes in img_dict.items():
            # 转为 base64 传入 Celery（任务参数需可序列化）
            image_map_base64[barcode] = base64.b64encode(img_bytes).decode("utf-8")

    # 3. 创建任务记录
    total = len(valid_records)
    task = import_service.create_task(
        db,
        task_name=task_name or f"文件导入-{excel_file.filename}",
        source="file",
        total_count=total,
        conflict_strategy=conflict_strategy,
        transaction_mode=transaction_mode,
        created_by=current_user.username,
    )
    # 校验失败的记录也加入 fail_list
    if invalid_records:
        import_service.update_task_status(
            task.task_id, "pending",
            fail_count=len(invalid_records),
            fail_detail=[{"barcode": r.get("barcode", ""), "reason": r["reason"]} for r in invalid_records],
        )

    # 4. 投递异步任务（轻量模式下同步执行）
    submit_import_file(
        task_id=task.task_id,
        records=valid_records,
        image_map_base64=image_map_base64,
        conflict_strategy=conflict_strategy,
        transaction_mode=transaction_mode,
    )
    return {"task_id": task.task_id, "total": total, "message": "任务已提交，处理中"}


@router.post("/push", response_model=dict, summary="方案B：API 批量推送商品")
def push_import(
    req: GoodsPushRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("operator", "admin")),
):
    """方案B：对外 API，接收 JSON 数组批量推送商品

    供超市 ERP 系统对接，一次性传入多条商品完整信息（含 base64 图片）。
    """
    if not req.items:
        raise HTTPException(status_code=400, detail="items 不能为空")

    # 转为 records + image_map_base64
    records = []
    image_map_base64 = {}
    for item in req.items:
        records.append({
            "barcode": item.barcode,
            "goods_name": item.goods_name,
            "category": item.category,
            "spec": item.spec,
            "retail_price": float(item.retail_price),
            "cost_price": float(item.cost_price) if item.cost_price else None,
            "shelf_no": item.shelf_no,
            "stock": item.stock,
            "supplier": item.supplier,
            "description": item.description,
        })
        # base64 图片直接用
        b64 = item.image_base64
        if "," in b64 and b64.startswith("data:"):
            b64 = b64.split(",", 1)[1]
        image_map_base64[item.barcode] = b64

    # 字段校验
    valid_records, invalid_records = validate_records(records)

    task = import_service.create_task(
        db,
        task_name=f"API推送-{len(req.items)}条",
        source="api",
        total_count=len(valid_records),
        conflict_strategy=req.conflict_strategy,
        transaction_mode=req.transaction_mode,
        created_by=current_user.username,
    )

    submit_import_api(
        task_id=task.task_id,
        records=valid_records,
        image_map_base64=image_map_base64,
        conflict_strategy=req.conflict_strategy,
        transaction_mode=req.transaction_mode,
    )
    return {"task_id": task.task_id, "total": len(valid_records), "message": "任务已提交"}


@router.get("/template", summary="下载 Excel 导入模板")
def download_template(_=Depends(get_current_user)):
    """下载 Excel 批量导入模板（含字段说明）"""
    from fastapi import Response
    import io
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "商品导入模板"
    # 表头
    headers = ["barcode", "goods_name", "category", "spec", "retail_price",
               "cost_price", "shelf_no", "stock", "supplier", "description"]
    ws.append(headers)
    # 示例行
    ws.append(["6901234567890", "可口可乐 330ml", "饮料", "330ml瓶装", 3.5, 2.5, "A-01", 100, "中粮可口可乐", "经典碳酸饮料"])
    ws.append(["6901234567891", "康师傅红烧牛肉面", "方便面", "105g袋装", 4.5, 3.0, "B-02", 200, "康师傅", "红烧牛肉味方便面"])
    # 列宽自适应
    for col in ws.columns:
        max_len = max(len(str(c.value)) if c.value else 0 for c in col)
        ws.column_dimensions[col[0].column_letter].width = max_len + 4

    buf = io.BytesIO()
    wb.save(buf)
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=goods_import_template.xlsx"},
    )


@router.get("/tasks", response_model=ImportTaskListOut, summary="导入任务列表")
def list_tasks(
    page: int = 1,
    page_size: int = 20,
    status: str = None,
    db: Session = Depends(get_db),
    _=Depends(require_role("operator", "admin")),
):
    """分页查询导入任务列表"""
    from sqlalchemy import desc
    q = db.query(ImportTask)
    if status:
        q = q.filter(ImportTask.status == status)
    total = q.count()
    items = q.order_by(desc(ImportTask.created_at)).offset((page - 1) * page_size).limit(page_size).all()
    return ImportTaskListOut(total=total, page=page, page_size=page_size, items=items)


@router.get("/tasks/{task_id}", response_model=ImportTaskOut, summary="任务详情/进度")
def get_task(task_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """查询任务进度和详情"""
    task = db.query(ImportTask).filter(ImportTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.get("/tasks/{task_id}/report", summary="下载导入报告")
def download_report(task_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """下载导入报告 CSV"""
    from fastapi import Response
    from app.services import storage_service
    import json

    task = db.query(ImportTask).filter(ImportTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.report_path:
        # 未生成报告，直接生成
        report_bytes = import_service.build_report(task)
    else:
        report_bytes = storage_service.download_file(task.report_path)
    return Response(
        content=report_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={task_id}_report.csv"},
    )
