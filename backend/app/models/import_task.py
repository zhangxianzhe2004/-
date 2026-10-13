"""批量导入任务表 ORM 模型"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime
from app.database import Base


class ImportTask(Base):
    """批量导入任务表：记录每次导入任务的状态与结果"""

    __tablename__ = "goods_import_task"

    task_id = Column(String(64), primary_key=True, comment="任务ID")
    task_name = Column(String(255), nullable=True, comment="任务名称")
    source = Column(String(16), nullable=False, default="file", comment="来源：file/api")
    status = Column(String(16), nullable=False, default="pending", comment="状态")
    total_count = Column(Integer, nullable=False, default=0, comment="总条数")
    success_count = Column(Integer, nullable=False, default=0, comment="成功条数")
    fail_count = Column(Integer, nullable=False, default=0, comment="失败条数")
    fail_detail = Column(Text, nullable=True, comment="失败明细 JSON")
    conflict_strategy = Column(String(16), nullable=False, default="skip", comment="冲突策略")
    transaction_mode = Column(String(16), nullable=False, default="partial", comment="事务模式")
    report_path = Column(String(512), nullable=True, comment="导入报告地址")
    error_msg = Column(Text, nullable=True, comment="任务级错误")
    created_by = Column(String(64), nullable=True, comment="创建人")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    finished_at = Column(DateTime, nullable=True, comment="完成时间")
