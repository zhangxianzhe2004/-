"""多模态检索功能测试脚本

测试内容：
1. 条码精确检索
2. 文本检索（"红色瓶装可乐"）
3. 图片检索（上传商品图片）
4. 混合检索（图文同时输入）
5. 检索响应时间验证（< 500ms）

运行方式：
    cd backend
    python -m tests.test_search

前置条件：
    - 已运行 test_import.py 导入测试商品
    - FastAPI 后端已启动
"""

import time
import io
import requests
from PIL import Image

BASE = "http://127.0.0.1:8000/api"
USERNAME = "staff"
PASSWORD = "123456"


def login():
    """登录"""
    r = requests.post(f"{BASE}/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert r.status_code == 200, f"登录失败：{r.text}"
    return r.json()["access_token"]


def test_barcode_search(token):
    """条码精确检索"""
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE}/search/barcode/6900000000011", headers=headers)
    assert r.status_code == 200
    data = r.json()
    print(f"[条码检索] 耗时 {data['cost_ms']}ms，结果 {data['total']} 条")
    for item in data["items"]:
        print(f"  - {item['barcode']} {item['goods_name']} (score={item['score']})")
    assert data["total"] == 1, "条码检索应返回 1 条"
    return data["cost_ms"]


def test_text_search(token):
    """文本检索"""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"query": "红色瓶装可乐", "top_n": 5, "threshold": 0.1}
    r = requests.post(f"{BASE}/search/text", headers=headers, json=payload)
    assert r.status_code == 200, f"文本检索失败：{r.text}"
    data = r.json()
    print(f"[文本检索] '红色瓶装可乐' 耗时 {data['cost_ms']}ms，结果 {data['total']} 条")
    for item in data["items"]:
        print(f"  - {item['barcode']} {item['goods_name']} (score={item['score']:.3f})")
    return data["cost_ms"]


def test_image_search(token):
    """图片检索：上传一张红色纯色图片"""
    headers = {"Authorization": f"Bearer {token}"}
    # 生成红色 224x224 图片
    img = Image.new("RGB", (224, 224), (231, 76, 60))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    files = {"file": ("test.jpg", buf, "image/jpeg")}
    data = {"top_n": "5", "threshold": "0.1"}
    r = requests.post(f"{BASE}/search/image", headers=headers, files=files, data=data)
    assert r.status_code == 200, f"图片检索失败：{r.text}"
    result = r.json()
    print(f"[图片检索] 红色图片 耗时 {result['cost_ms']}ms，结果 {result['total']} 条")
    for item in result["items"]:
        print(f"  - {item['barcode']} {item['goods_name']} (score={item['score']:.3f})")
    return result["cost_ms"]


def test_hybrid_search(token):
    """混合检索：图片 + 文本"""
    headers = {"Authorization": f"Bearer {token}"}
    img = Image.new("RGB", (224, 224), (231, 76, 60))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    files = {"file": ("test.jpg", buf, "image/jpeg")}
    data = {
        "text_query": "可乐",
        "top_n": "5",
        "threshold": "0.1",
        "image_weight": "0.6",
        "text_weight": "0.4",
    }
    r = requests.post(f"{BASE}/search/hybrid", headers=headers, files=files, data=data)
    assert r.status_code == 200, f"混合检索失败：{r.text}"
    result = r.json()
    print(f"[混合检索] 图+文 耗时 {result['cost_ms']}ms，结果 {result['total']} 条")
    for item in result["items"]:
        print(f"  - {item['barcode']} {item['goods_name']} (score={item['score']:.3f})")
    return result["cost_ms"]


def main():
    print("=" * 60)
    print("  多模态检索功能测试")
    print("=" * 60)
    token = login()
    print("[登录成功]\n")

    times = []
    print("--- 1. 条码精确检索 ---")
    times.append(("条码检索", test_barcode_search(token)))

    print("\n--- 2. 文本检索 ---")
    times.append(("文本检索", test_text_search(token)))

    print("\n--- 3. 图片检索 ---")
    times.append(("图片检索", test_image_search(token)))

    print("\n--- 4. 混合检索 ---")
    times.append(("混合检索", test_hybrid_search(token)))

    # 性能验证
    print("\n" + "=" * 60)
    print("  响应时间验证（要求 < 500ms）")
    print("=" * 60)
    all_pass = True
    for name, t in times:
        ok = "✓" if t < 500 else "✗"
        print(f"  {name}: {t}ms {ok}")
        if t >= 500:
            all_pass = False
    if all_pass:
        print("\n所有检索响应时间均 < 500ms，达标。")
    else:
        print("\n部分检索响应超 500ms（首次检索会触发模型加载，建议预热）。")


if __name__ == "__main__":
    main()
