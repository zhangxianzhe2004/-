"""Excel / CSV 文件解析模块

负责解析批量导入的商品清单文件，校验字段，返回结构化数据。
图片按文件名（barcode.jpg）与商品行匹配，由调用方处理。
"""

import io
import os
from typing import Optional

import pandas as pd

from app.schemas.goods import GoodsCreate


# Excel 表头字段映射（支持中英文表头）
COLUMN_MAP = {
    # 条码
    "barcode": ["barcode", "条码", "商品条码"],
    # 商品名称
    "goods_name": ["goods_name", "商品名称", "名称"],
    # 分类
    "category": ["category", "商品分类", "分类"],
    # 规格
    "spec": ["spec", "商品规格", "规格"],
    # 零售价
    "retail_price": ["retail_price", "零售价", "价格"],
    # 进价
    "cost_price": ["cost_price", "进价", "成本价"],
    # 货架号
    "shelf_no": ["shelf_no", "货架编号", "货架"],
    # 库存
    "stock": ["stock", "库存"],
    # 供应商
    "supplier": ["supplier", "供应商"],
    # 描述
    "description": ["description", "商品描述", "描述"],
}

# 必填字段
REQUIRED_FIELDS = ["barcode", "goods_name", "category", "spec", "retail_price"]


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """将中英文表头统一标准化为英文字段名"""
    rename_dict = {}
    for standard_name, aliases in COLUMN_MAP.items():
        for alias in aliases:
            if alias in df.columns:
                rename_dict[alias] = standard_name
                break
    df = df.rename(columns=rename_dict)
    return df


def parse_excel(file_bytes: bytes, filename: str) -> list[dict]:
    """解析 Excel/CSV 文件，返回原始字典列表

    Args:
        file_bytes: 文件字节内容
        filename: 文件名（用于判断 xlsx/csv）
    Returns:
        list[dict]: 每条商品的字段字典
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".csv":
        # CSV 尝试多种编码
        for encoding in ["utf-8", "gbk", "gb2312"]:
            try:
                df = pd.read_csv(io.BytesIO(file_bytes), encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("CSV 文件编码无法识别，请使用 UTF-8 或 GBK 编码")
    else:
        # Excel xlsx/xls
        df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")

    # 去除完全空行
    df = df.dropna(how="all")
    # 标准化表头
    df = _normalize_columns(df)

    # 转为字典列表，NaN 转为 None
    records = []
    for _, row in df.iterrows():
        record = {}
        for col in COLUMN_MAP.keys():
            val = row.get(col)
            if pd.isna(val):
                record[col] = None
            else:
                record[col] = val
        records.append(record)
    return records


def validate_records(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """校验商品记录，返回（有效记录, 失败记录）

    校验内容：
    - 必填字段非空
    - barcode 非空
    - retail_price 合法数字
    """
    valid = []
    invalid = []
    for idx, rec in enumerate(records):
        errors = []
        # 必填字段校验
        for field in REQUIRED_FIELDS:
            val = rec.get(field)
            if val is None or str(val).strip() == "":
                errors.append(f"必填字段 {field} 为空")
        # barcode 校验
        barcode = rec.get("barcode")
        if barcode is not None and not str(barcode).strip():
            errors.append("条码不能为空")
        if barcode is not None:
            rec["barcode"] = str(barcode).strip()
        # 零售价校验
        price = rec.get("retail_price")
        if price is not None:
            try:
                rec["retail_price"] = float(price)
            except (ValueError, TypeError):
                errors.append(f"零售价非数字：{price}")
        # 库存转 int
        if rec.get("stock") is not None:
            try:
                rec["stock"] = int(float(rec["stock"]))
            except (ValueError, TypeError):
                rec["stock"] = 0

        if errors:
            invalid.append({"row": idx + 2, "barcode": str(barcode), "reason": "; ".join(errors)})
        else:
            valid.append(rec)
    return valid, invalid


def extract_image_names_from_zip(zip_bytes: bytes) -> dict[str, bytes]:
    """从图片压缩包解压，返回 {barcode: 图片字节}

    约定：图片文件名 = 商品条码.jpg（或 .png/.jpeg）
    """
    import zipfile

    result = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.startswith("__MACOSX") or name.endswith("/"):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
                continue
            # 取文件名（不含扩展名）作为 barcode
            barcode = os.path.splitext(os.path.basename(name))[0]
            result[barcode] = zf.read(name)
    return result
