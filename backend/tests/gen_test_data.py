"""测试数据生成器

生成测试用的：
1. Excel 商品清单（goods_test.xlsx）
2. 图片压缩包（goods_images.zip，图片命名=条码.jpg，使用纯色块模拟商品图）

运行方式：
    cd backend
    python -m tests.gen_test_data
"""

import os
import zipfile
import io
from PIL import Image

import pandas as pd

# 测试商品清单（模拟超市常见商品）
TEST_GOODS = [
    {"barcode": "6900000000011", "goods_name": "可口可乐 330ml", "category": "饮料", "spec": "330ml瓶装",
     "retail_price": 3.5, "cost_price": 2.5, "shelf_no": "A-01", "stock": 120, "supplier": "中粮可口可乐", "description": "经典碳酸饮料 红色瓶装可乐"},
    {"barcode": "6900000000028", "goods_name": "康师傅红烧牛肉面", "category": "方便面", "spec": "105g袋装",
     "retail_price": 4.5, "cost_price": 3.0, "shelf_no": "B-02", "stock": 200, "supplier": "康师傅", "description": "红烧牛肉味方便面"},
    {"barcode": "6900000000035", "goods_name": "伊利纯牛奶 250ml", "category": "乳制品", "spec": "250ml盒装",
     "retail_price": 3.8, "cost_price": 2.8, "shelf_no": "C-03", "stock": 150, "supplier": "伊利集团", "description": "纯牛奶 高钙 营养早餐"},
    {"barcode": "6900000000042", "goods_name": "农夫山泉 550ml", "category": "饮料", "spec": "550ml瓶装",
     "retail_price": 2.0, "cost_price": 1.0, "shelf_no": "A-02", "stock": 300, "supplier": "农夫山泉", "description": "天然饮用水 矿泉水"},
    {"barcode": "6900000000059", "goods_name": "乐事薯片 原味", "category": "零食", "spec": "75g袋装",
     "retail_price": 7.5, "cost_price": 5.0, "shelf_no": "D-01", "stock": 80, "supplier": "百事食品", "description": "原味薯片 香脆零食"},
    {"barcode": "6900000000066", "goods_name": "统一老坛酸菜面", "category": "方便面", "spec": "115g袋装",
     "retail_price": 4.5, "cost_price": 3.0, "shelf_no": "B-03", "stock": 180, "supplier": "统一企业", "description": "老坛酸菜牛肉面 酸辣口味"},
    {"barcode": "6900000000073", "goods_name": "蒙牛酸酸乳", "category": "乳制品", "spec": "250ml盒装",
     "retail_price": 3.0, "cost_price": 2.0, "shelf_no": "C-04", "stock": 100, "supplier": "蒙牛乳业", "description": "酸酸乳 乳酸菌饮料 草莓味"},
    {"barcode": "6900000000080", "goods_name": "旺旺雪饼", "category": "零食", "spec": "50g袋装",
     "retail_price": 5.0, "cost_price": 3.5, "shelf_no": "D-02", "stock": 90, "supplier": "旺旺集团", "description": "雪饼 米饼 膨化食品"},
]

# 每种商品的代表色（生成纯色图片）
COLORS = ["#E74C3C", "#F39C12", "#3498DB", "#2ECC71", "#9B59B6", "#1ABC9C", "#E67E22", "#34495E"]


def gen_excel():
    """生成测试 Excel 清单"""
    df = pd.DataFrame(TEST_GOODS)
    out_path = "data/test_goods.xlsx"
    os.makedirs("data", exist_ok=True)
    df.to_excel(out_path, index=False)
    print(f"[Excel 已生成] {os.path.abspath(out_path)}（{len(TEST_GOODS)} 条商品）")
    return out_path


def gen_image_zip():
    """生成图片压缩包，每张图为纯色块 + 商品名文字"""
    zip_path = "data/test_goods_images.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(zip_path, "w") as zf:
        for idx, g in enumerate(TEST_GOODS):
            # 生成 224x224 纯色图片，中间写商品名
            color = COLORS[idx % len(COLORS)]
            r = int(color[1:3], 16)
            g_ = int(color[3:5], 16)
            b = int(color[5:7], 16)
            img = Image.new("RGB", (224, 224), (r, g_, b))
            # 写入压缩包
            img_buf = io.BytesIO()
            img.save(img_buf, format="JPEG")
            zf.writestr(f"{g['barcode']}.jpg", img_buf.getvalue())
    print(f"[图片 zip 已生成] {os.path.abspath(zip_path)}（{len(TEST_GOODS)} 张图片）")
    return zip_path


def main():
    print("=" * 50)
    print("  生成测试数据（Excel + 图片 zip）")
    print("=" * 50)
    os.makedirs("data", exist_ok=True)
    gen_excel()
    gen_image_zip()
    print("\n生成完毕，可用于批量导入测试：")
    print("  Excel 清单：data/test_goods.xlsx")
    print("  图片压缩包：data/test_goods_images.zip")


if __name__ == "__main__":
    main()
