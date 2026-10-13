"""生成 Excel 导入模板静态文件

运行本脚本会在 backend/templates/ 目录下生成 goods_import_template.xlsx
启动后端后也可通过 http://127.0.0.1:8000/api/import/template 动态下载。
"""

import os
import openpyxl


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "goods_import_template.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "商品导入模板"
    headers = ["barcode", "goods_name", "category", "spec", "retail_price",
               "cost_price", "shelf_no", "stock", "supplier", "description"]
    ws.append(headers)
    ws.append(["6901234567890", "可口可乐 330ml", "饮料", "330ml瓶装", 3.5, 2.5, "A-01", 100, "中粮可口可乐", "经典碳酸饮料"])
    ws.append(["6901234567891", "康师傅红烧牛肉面", "方便面", "105g袋装", 4.5, 3.0, "B-02", 200, "康师傅", "红烧牛肉味方便面"])
    for col in ws.columns:
        max_len = max(len(str(c.value)) if c.value else 0 for c in col)
        ws.column_dimensions[col[0].column_letter].width = max_len + 4
    wb.save(out)
    print(f"模板已生成：{out}")


if __name__ == "__main__":
    main()
