"""批量导入功能测试脚本

测试内容：
1. 方案A：文件导入（Excel + 图片zip）
2. 方案B：API 批量推送
3. 任务进度查询
4. 导入结果校验

运行方式：
    cd backend
    python -m tests.test_import

前置条件：
    - MySQL / Redis / MinIO 已启动
    - FastAPI 后端已启动（127.0.0.1:8000）
    - Celery worker 已启动
    - 已运行 gen_test_data.py 生成测试数据
"""

import time
import requests

# 后端地址
BASE = "http://127.0.0.1:8000/api"

# 测试账号
USERNAME = "admin"
PASSWORD = "123456"


def login():
    """登录获取 Token"""
    r = requests.post(f"{BASE}/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert r.status_code == 200, f"登录失败：{r.text}"
    token = r.json()["access_token"]
    print(f"[登录成功] 用户 {USERNAME}")
    return token


def test_file_import(token):
    """方案A：文件导入测试"""
    headers = {"Authorization": f"Bearer {token}"}
    # 1. 准备文件
    excel_path = "data/test_goods.xlsx"
    zip_path = "data/test_goods_images.zip"

    # 2. 上传导入
    with open(excel_path, "rb") as f_excel, open(zip_path, "rb") as f_zip:
        files = {
            "excel_file": ("test_goods.xlsx", f_excel, "application/vnd.ms-excel"),
            "image_zip": ("test_goods_images.zip", f_zip, "application/zip"),
        }
        data = {
            "conflict_strategy": "overwrite",
            "transaction_mode": "partial",
            "task_name": "自动化测试导入",
        }
        r = requests.post(f"{BASE}/import/upload", headers=headers, files=files, data=data)
    assert r.status_code == 200, f"上传失败：{r.text}"
    result = r.json()
    print(f"[文件导入] 任务已提交：{result['task_id']}，共 {result['total']} 条")
    return result["task_id"]


def test_api_push(token):
    """方案B：API 批量推送测试"""
    headers = {"Authorization": f"Bearer {token}"}
    import base64
    # 用一张纯色图作为 base64
    from PIL import Image
    import io
    img = Image.new("RGB", (224, 224), (231, 76, 60))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    payload = {
        "items": [
            {
                "barcode": "6900000000097",
                "goods_name": "测试商品-API推送",
                "category": "测试",
                "spec": "100g",
                "retail_price": 9.9,
                "image_base64": img_b64,
            }
        ],
        "conflict_strategy": "overwrite",
        "transaction_mode": "partial",
    }
    r = requests.post(f"{BASE}/import/push", headers=headers, json=payload)
    assert r.status_code == 200, f"API 推送失败：{r.text}"
    result = r.json()
    print(f"[API 推送] 任务已提交：{result['task_id']}，共 {result['total']} 条")
    return result["task_id"]


def wait_task(token, task_id, timeout=120):
    """轮询任务状态直至完成"""
    headers = {"Authorization": f"Bearer {token}"}
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(f"{BASE}/import/tasks/{task_id}", headers=headers)
        assert r.status_code == 200
        task = r.json()
        status = task["status"]
        print(f"  [任务进度] {task['success_count']}/{task['total_count']} 状态={status}")
        if status in ("success", "partial", "failed"):
            return task
        time.sleep(3)
    print("  [超时] 任务未在规定时间内完成")
    return None


def verify_goods(token):
    """校验导入结果：查询商品列表"""
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE}/goods?page=1&page_size=20", headers=headers)
    assert r.status_code == 200
    data = r.json()
    print(f"[校验] 当前商品总数：{data['total']}")
    for g in data["items"][:5]:
        print(f"  - {g['barcode']} {g['goods_name']} ¥{g['retail_price']}")
    return data["total"]


def main():
    print("=" * 60)
    print("  批量导入功能测试")
    print("=" * 60)
    token = login()

    # 方案A：文件导入
    print("\n--- 测试方案A：文件导入 ---")
    task_id = test_file_import(token)
    task = wait_task(token, task_id)
    if task:
        print(f"  [完成] 成功 {task['success_count']} 条，失败 {task['fail_count']} 条")

    # 方案B：API 推送
    print("\n--- 测试方案B：API 推送 ---")
    task_id2 = test_api_push(token)
    wait_task(token, task_id2)

    # 校验
    print("\n--- 校验导入结果 ---")
    verify_goods(token)
    print("\n批量导入测试完成。")


if __name__ == "__main__":
    main()
