"""批量导入任务 Pydantic 模型"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class ImportTaskOut(BaseModel):
    """导入任务输出"""
    task_id: str
    task_name: Optional[str] = None
    source: str
    status: str
    total_count: int
    success_count: int
    fail_count: int
    fail_detail: Optional[Any] = None
    conflict_strategy: str
    transaction_mode: str
    report_path: Optional[str] = None
    error_msg: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ImportTaskListOut(BaseModel):
    """任务列表分页输出"""
    total: int
    page: int
    page_size: int
    items: list[ImportTaskOut]


class ImportUploadRequest(BaseModel):
    """上传导入请求参数（表单字段）"""
    conflict_strategy: str = "skip"      # skip/overwrite/abort
    transaction_mode: str = "partial"    # atomic/partial
