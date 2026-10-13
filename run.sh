#!/bin/bash
# =============================================================
# 超市商品多模态检索系统 - 一键启动脚本
#
# 功能：
#   1. 检查/创建 Python 虚拟环境，安装依赖
#   2. 启动 FastAPI 后端（轻量模式：SQLite + 本地存储，无需中间件）
#   3. 启动 Vue3 前端开发服务器
#   4. 自动生成测试数据并完成批量导入
#   5. 演示条码检索 / 文本检索，输出结果
#   6. 打印访问地址和登录账号
#
# 用法：
#   chmod +x run.sh   （首次运行前赋予执行权限）
#   ./run.sh          启动全部服务
#   ./run.sh stop     停止全部服务
# =============================================================

set -e

# ---------- 路径配置 ----------
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$PROJECT_DIR/.venv"
UV_BIN="$HOME/.local/bin/uv"
BACKEND_PORT=8000
FRONTEND_PORT=5173
LOG_DIR="$PROJECT_DIR/logs"

# ---------- 颜色输出 ----------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 无色

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_step()  { echo -e "${BLUE}[STEP]${NC} $1"; }

# =============================================================
# 停止服务：./run.sh stop
# =============================================================
stop_services() {
    log_step "停止所有服务..."
    pkill -f "uvicorn app.main:app" 2>/dev/null && log_info "后端已停止" || log_warn "后端未在运行"
    pkill -f "vite" 2>/dev/null && log_info "前端已停止" || log_warn "前端未在运行"
    exit 0
}

# 支持 stop 参数
if [ "$1" == "stop" ]; then
    stop_services
fi

echo "=============================================================="
echo "  超市商品多模态检索系统 - 一键启动"
echo "  模式：轻量模式（SQLite + 本地存储 + 内存缓存，无需中间件）"
echo "=============================================================="

# =============================================================
# 第一步：清理旧进程，防止端口占用
# =============================================================
log_step "第一步：清理旧进程..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 1
mkdir -p "$LOG_DIR"

# =============================================================
# 第二步：准备 Python 虚拟环境和依赖
# =============================================================
log_step "第二步：检查 Python 虚拟环境..."
if [ ! -d "$VENV_DIR" ]; then
    log_info "虚拟环境不存在，使用 uv 创建（Python 3.11）..."
    "$UV_BIN" venv --python 3.11 "$VENV_DIR"
    log_info "安装后端依赖..."
    "$UV_BIN" pip install -r "$PROJECT_DIR/requirements-lite.txt"
else
    log_info "虚拟环境已存在，跳过创建"
fi

PYTHON="$VENV_DIR/bin/python"

# =============================================================
# 第三步：启动 FastAPI 后端
# =============================================================
log_step "第三步：启动 FastAPI 后端（端口 $BACKEND_PORT）..."
cd "$BACKEND_DIR"
nohup "$VENV_DIR/bin/uvicorn" app.main:app --host 0.0.0.0 --port $BACKEND_PORT \
    > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$LOG_DIR/backend.pid"

# 等待后端就绪（最多 30 秒）
log_info "等待后端启动..."
for i in $(seq 1 30); do
    if curl -s "http://127.0.0.1:$BACKEND_PORT/" > /dev/null 2>&1; then
        log_info "后端启动成功 ✓"
        break
    fi
    if [ $i -eq 30 ]; then
        log_warn "后端启动超时，请查看日志：$LOG_DIR/backend.log"
        exit 1
    fi
    sleep 1
done

# =============================================================
# 第四步：启动 Vue3 前端
# =============================================================
log_step "第四步：启动 Vue3 前端（端口 $FRONTEND_PORT）..."
cd "$FRONTEND_DIR"

# 首次运行安装 npm 依赖
if [ ! -d "node_modules" ]; then
    log_info "首次运行，安装前端依赖（可能需要几分钟）..."
    npm install
fi

nohup npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$LOG_DIR/frontend.pid"

# 等待前端就绪（最多 60 秒）
log_info "等待前端启动..."
for i in $(seq 1 60); do
    if curl -s "http://127.0.0.1:$FRONTEND_PORT/" > /dev/null 2>&1; then
        log_info "前端启动成功 ✓"
        break
    fi
    if [ $i -eq 60 ]; then
        log_warn "前端启动超时，请查看日志：$LOG_DIR/frontend.log"
        exit 1
    fi
    sleep 1
done

# =============================================================
# 第五步：登录获取 Token
# =============================================================
log_step "第五步：登录系统（admin / 123456）..."
LOGIN_RESP=$(curl -s -X POST "http://127.0.0.1:$BACKEND_PORT/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"123456"}')
TOKEN=$(echo "$LOGIN_RESP" | "$PYTHON" -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    log_warn "登录失败：$LOGIN_RESP"
    exit 1
fi
log_info "登录成功，已获取 Token"

# =============================================================
# 第六步：生成测试数据并批量导入
# =============================================================
log_step "第六步：检查商品数据，为空则生成并导入测试数据..."
GOODS_COUNT=$(curl -s "http://127.0.0.1:$BACKEND_PORT/api/goods" \
    -H "Authorization: Bearer $TOKEN" | "$PYTHON" -c "import sys,json; print(json.load(sys.stdin)['total'])" 2>/dev/null)

if [ "$GOODS_COUNT" == "0" ]; then
    log_info "商品库为空，生成测试数据（8 条商品 + 图片）..."
    cd "$BACKEND_DIR"
    "$PYTHON" -m tests.gen_test_data > /dev/null 2>&1

    log_info "通过 API 批量导入商品（Excel + 图片 zip）..."
    IMPORT_RESP=$(curl -s -X POST "http://127.0.0.1:$BACKEND_PORT/api/import/upload" \
        -H "Authorization: Bearer $TOKEN" \
        -F "excel_file=@data/test_goods.xlsx" \
        -F "image_zip=@data/test_goods_images.zip" \
        -F "conflict_strategy=overwrite" \
        -F "transaction_mode=partial" \
        -F "task_name=一键启动-测试导入")
    TASK_ID=$(echo "$IMPORT_RESP" | "$PYTHON" -c "import sys,json; print(json.load(sys.stdin)['task_id'])" 2>/dev/null)

    # 等待导入完成（轻量模式同步执行，通常很快）
    sleep 3
    TASK_STATUS=$(curl -s "http://127.0.0.1:$BACKEND_PORT/api/import/tasks/$TASK_ID" \
        -H "Authorization: Bearer $TOKEN" | "$PYTHON" -c "
import sys,json
t = json.load(sys.stdin)
print(f\"{t['status']}|{t['success_count']}|{t['fail_count']}\")" 2>/dev/null)
    IFS='|' read -r STATUS SUCCESS FAIL <<< "$TASK_STATUS"
    log_info "导入完成：状态=$STATUS，成功=$SUCCESS 条，失败=$FAIL 条"
else
    log_info "商品库已有 $GOODS_COUNT 条商品，跳过导入"
fi

# =============================================================
# 第七步：演示检索功能
# =============================================================
log_step "第七步：演示检索功能..."

echo ""
echo "---------- ① 条码精确检索（6900000000011）----------"
curl -s "http://127.0.0.1:$BACKEND_PORT/api/search/barcode/6900000000011" \
    -H "Authorization: Bearer $TOKEN" | "$PYTHON" -c "
import sys,json
r = json.load(sys.stdin)
for item in r['items']:
    print(f\"  ✓ {item['goods_name']} | 条码:{item['barcode']} | 分类:{item['category']} | 价格:¥{item['retail_price']} | 货架:{item['shelf_no']} | 库存:{item['stock']} | 相似度:{item['score']}\")
print(f\"  耗时: {r['cost_ms']}ms\")"

echo ""
echo "---------- ② 文本检索（可乐）----------"
curl -s -X POST "http://127.0.0.1:$BACKEND_PORT/api/search/text" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"query":"可乐","top_n":5}' | "$PYTHON" -c "
import sys,json
r = json.load(sys.stdin)
for item in r['items']:
    print(f\"  ✓ {item['goods_name']} | 条码:{item['barcode']} | 价格:¥{item['retail_price']} | 相似度:{item['score']}\")
print(f\"  耗时: {r['cost_ms']}ms\")"

echo ""
echo "---------- ③ 文本检索（方便面）----------"
curl -s -X POST "http://127.0.0.1:$BACKEND_PORT/api/search/text" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"query":"方便面","top_n":5}' | "$PYTHON" -c "
import sys,json
r = json.load(sys.stdin)
for item in r['items']:
    print(f\"  ✓ {item['goods_name']} | 条码:{item['barcode']} | 价格:¥{item['retail_price']} | 相似度:{item['score']}\")
print(f\"  耗时: {r['cost_ms']}ms\")"

# =============================================================
# 第八步：打印访问信息
# =============================================================
echo ""
echo "=============================================================="
echo "  🎉 系统启动完成！"
echo "=============================================================="
echo ""
echo "  📱 前端管理后台：http://127.0.0.1:$FRONTEND_PORT"
echo "  🔧 后端 API：    http://127.0.0.1:$BACKEND_PORT"
echo "  📖 API 文档：    http://127.0.0.1:$BACKEND_PORT/docs"
echo ""
echo "  👤 登录账号（密码均为 123456）："
echo "     admin    - 管理员（全部权限）"
echo "     operator - 运营（批量导入）"
echo "     staff    - 店员（仅检索）"
echo ""
echo "  🧪 测试功能："
echo "     - 商品列表：查看 8 条已导入商品"
echo "     - 多模态检索：条码检索 6900000000011 / 文本检索「可乐」"
echo "     - 批量导入：上传 data/test_goods.xlsx + data/test_goods_images.zip"
echo ""
echo "  📋 日志文件："
echo "     后端：$LOG_DIR/backend.log"
echo "     前端：$LOG_DIR/frontend.log"
echo ""
echo "  🛑 停止系统：./run.sh stop"
echo "=============================================================="
