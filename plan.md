# 超市商品多模态检索系统 - 项目规划文档

> 版本：v1.0  |  规划日期：2026-10-12
> 核心目标：支持图片/文字多模态检索商品；新品支持批量整体导入，无需逐个表单录入。

---

## 一、项目概述

### 1.1 业务背景
超市内部使用场景：
- **店员**：拍照搜商品 / 文字描述搜商品（快速定位商品位置、价格、库存）
- **运营**：一次性批量导入一批新品完整信息（Excel + 图片压缩包）
- **管理员**：全权限管理商品、任务、用户

### 1.2 核心能力
| 能力 | 说明 |
|------|------|
| 图片检索 | 上传商品照片 → CLIP 提取图像向量 → Milvus 召回相似商品 |
| 文本检索 | 输入文字描述（如"红色瓶装可乐"）→ BGE 文本向量 → Milvus 检索 |
| 条码精确检索 | MySQL 精确匹配 barcode，毫秒级响应 |
| 混合检索 | 图文同时输入 → 加权融合图像向量 + 文本向量结果 |
| 阈值控制 | 低于相似度阈值不返回，TopN 候选商品 |
| 批量导入（方案A） | Excel/CSV + 图片压缩包，按 barcode 匹配图片 |
| 批量导入（方案B） | API 接收 JSON 数组（支持 base64 图片），供 ERP 对接 |

---

## 二、系统架构（严格分层）

```
┌─────────────────────────────────────────────────────────────┐
│                       接入层                                 │
│  管理后台Web(Vue3)  +  H5拍照检索页  +  批量导入API          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                     业务服务层 (FastAPI)                     │
│  1. 多模态检索服务：CLIP + BGE + Milvus                      │
│  2. 批量导入服务：Excel解析 + 图片预处理 + 校验 + 异步向量    │
│  3. 商品元数据服务 (MySQL CRUD)                              │
│  4. 任务队列服务 (Redis + Celery)                            │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                        存储层                                │
│  MySQL(元数据)  MinIO(原图+缩略图)  Milvus(向量)  Redis(缓存)│
└─────────────────────────────────────────────────────────────┘
```

### 2.1 技术栈
| 层 | 技术选型 |
|----|----------|
| 后端框架 | Python + FastAPI |
| 图像向量 | CLIP（openai-clip / 中文 CLIP） |
| 文本向量 | BGE（bge-small-zh） |
| 向量库 | Milvus-Lite（本地轻量版） |
| 关系库 | MySQL 8.0 |
| 任务队列 | Redis + Celery |
| 对象存储 | MinIO |
| 前端 | Vue3 + Element Plus |
| 文件解析 | pandas（Excel/CSV） |
| 图片处理 | Pillow |

---

## 三、数据库设计

### 3.1 商品主表 `goods`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| barcode | VARCHAR(64) PK | ✅ | 商品条码，唯一主键 |
| goods_name | VARCHAR(255) | ✅ | 商品名称 |
| category | VARCHAR(64) | ✅ | 商品分类 |
| spec | VARCHAR(128) | ✅ | 商品规格 |
| retail_price | DECIMAL(10,2) | ✅ | 零售价 |
| cost_price | DECIMAL(10,2) | ❌ | 进价 |
| shelf_no | VARCHAR(32) | ❌ | 货架编号 |
| stock | INT | ❌ | 库存 |
| supplier | VARCHAR(128) | ❌ | 供应商 |
| description | TEXT | ❌ | 商品描述（用于文本向量） |
| image_path | VARCHAR(512) | ✅ | 对象存储图片地址 |
| thumbnail_path | VARCHAR(512) | ❌ | 缩略图地址 |
| created_at | DATETIME | - | 创建时间 |
| updated_at | DATETIME | - | 更新时间 |

### 3.2 批量导入任务表 `goods_import_task`
| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | VARCHAR(64) PK | 任务ID |
| status | VARCHAR(16) | pending/processing/success/failed/partial |
| total_count | INT | 总条数 |
| success_count | INT | 成功条数 |
| fail_count | INT | 失败条数 |
| fail_detail | TEXT | 失败明细 JSON |
| conflict_strategy | VARCHAR(16) | skip/overwrite/abort |
| transaction_mode | VARCHAR(16) | atomic/partial |
| report_path | VARCHAR(512) | 导入报告文件地址 |
| created_at | DATETIME | 创建时间 |
| finished_at | DATETIME | 完成时间 |

### 3.3 用户表 `sys_user`（简易权限）
| 字段 | 说明 |
|------|------|
| user_id, username, password_hash, role(operator/staff/admin), created_at |

---

## 四、目录结构设计

```
超市商品多模态的检索系统/
├── plan.md                          # 本规划文档
├── env_setup.txt                    # 环境搭建文档（后续生成）
├── run_guide.txt                    # 运行操作手册（后续生成）
├── requirements.txt                 # Python 依赖
├── backend/                         # FastAPI 后端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI 入口
│   │   ├── config.py                # 配置管理
│   │   ├── database.py              # MySQL 连接
│   │   ├── deps.py                  # 依赖注入
│   │   ├── api/                     # 路由层
│   │   │   ├── __init__.py
│   │   │   ├── goods.py             # 商品 CRUD
│   │   │   ├── search.py            # 多模态检索
│   │   │   ├── import_task.py       # 批量导入
│   │   │   └── auth.py              # 登录/权限
│   │   ├── models/                  # 数据模型
│   │   │   ├── goods.py
│   │   │   ├── import_task.py
│   │   │   └── user.py
│   │   ├── schemas/                 # Pydantic 模型
│   │   ├── services/                # 业务服务
│   │   │   ├── search_service.py    # 检索服务
│   │   │   ├── import_service.py    # 导入服务
│   │   │   ├── vector_service.py    # 向量化服务
│   │   │   ├── storage_service.py   # MinIO 服务
│   │   │   └── cache_service.py     # Redis 缓存
│   │   ├── tasks/                   # Celery 异步任务
│   │   │   ├── celery_app.py
│   │   │   └── import_tasks.py
│   │   └── utils/                   # 工具函数
│   │       ├── excel_parser.py
│   │       ├── image_utils.py
│   │       └── clip_model.py
│   ├── sql/
│   │   └── init.sql                 # 建表 SQL
│   ├── templates/
│   │   └── goods_import_template.xlsx  # Excel 导入模板
│   └── tests/
│       ├── test_import.py
│       └── test_search.py
├── frontend/                        # Vue3 前端
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   ├── router/
│   │   ├── stores/
│   │   ├── api/
│   │   ├── views/
│   │   │   ├── Login.vue
│   │   │   ├── Layout.vue
│   │   │   ├── GoodsList.vue        # 商品列表
│   │   │   ├── GoodsEdit.vue        # 单条编辑
│   │   │   ├── ImportTask.vue       # 批量导入
│   │   │   ├── TaskList.vue         # 任务管理
│   │   │   └── SearchTest.vue       # 检索测试
│   │   └── components/
│   └── index.html
└── README.md                        # （不主动创建，按需）
```

---

## 五、开发阶段拆分（6 个阶段）

### 阶段 1：基础设施搭建 ⭐ 基础
- [x] 输出 plan.md（本文档）
- [ ] 后端骨架：FastAPI 入口、配置、MySQL 连接、目录结构
- [ ] 数据库建表 SQL（goods / goods_import_task / sys_user）
- [ ] requirements.txt 依赖清单
- [ ] 前端骨架：Vue3 + Element Plus + 路由 + 布局

### 阶段 2：商品元数据 CRUD + 权限
- [ ] 商品列表分页查询、单条编辑、删除接口
- [ ] 简易用户登录（JWT）+ 角色权限中间件
- [ ] 前端商品列表页、编辑页、登录页

### 阶段 3：多模态检索服务 ⭐ 核心
- [ ] CLIP 图像向量提取（加载本地模型）
- [ ] BGE 文本向量提取
- [ ] Milvus-Lite 集合初始化（image_vectors / text_vectors）
- [ ] 图片检索接口（上传 → 向量化 → Milvus 召回 → 阈值过滤 → TopN）
- [ ] 文本检索接口
- [ ] 条码精确检索接口（MySQL）
- [ ] 混合检索接口（图文加权融合）
- [ ] 阈值参数化 + TopN 参数
- [ ] 前端检索测试页（图片上传、文本输入、结果展示）

### 阶段 4：批量导入服务 ⭐⭐ 最高优先级
- [ ] Excel/CSV 解析模块（pandas）
- [ ] 图片压缩包处理（zip 解压，按 barcode 匹配）
- [ ] 字段校验 + 条码查重 + 冲突策略（skip/overwrite/abort）
- [ ] MinIO 上传原图 + 生成缩略图
- [ ] Celery 异步任务：批量生成图像向量 + 文本向量 → 写入 Milvus
- [ ] 事务模式：atomic（整批回滚）/ partial（失败导出）
- [ ] 导入报告生成（成功/失败明细 CSV）
- [ ] 任务进度查询接口
- [ ] API 批量推送接口（方案B：JSON + base64 图片）
- [ ] 前端批量导入页（上传 Excel + 图片 zip、选冲突策略、查进度、下报告）
- [ ] Excel 导入模板生成

### 阶段 5：测试脚本
- [ ] 批量导入测试脚本（造模拟数据 + 图片）
- [ ] 多模态检索测试脚本（图片/文本/条码/混合）
- [ ] 性能验证（响应时间 < 500ms）

### 阶段 6：交付文档
- [ ] env_setup.txt（Python 版本 + requirements + 中间件安装 + 报错排查）
- [ ] run_guide.txt（分步启动 + 操作指引 + 接口测试示例）
- [ ] API 接口文档（检索 + 批量导入）

---

## 六、关键设计决策

### 6.1 批量导入流程（方案A）
```
上传 Excel + 图片zip
   │
   ▼
Excel 解析 → 字段校验
   │
   ▼
条码查重 → 冲突策略判定（skip / overwrite / abort）
   │
   ▼
创建 import_task 记录（status=processing）→ 立即返回 task_id
   │
   ▼
Celery 异步任务：
   ├─ 解压图片 zip，按 barcode 匹配
   ├─ 图片预处理（压缩生成缩略图）→ 上传 MinIO
   ├─ 写入 MySQL（atomic 整批事务 / partial 逐条）
   ├─ CLIP 生成图像向量 → Milvus image_vectors
   └─ BGE 生成文本向量 → Milvus text_vectors
   │
   ▼
更新 task 状态（success / partial / failed）
生成导入报告 CSV → 上传 MinIO
   │
   ▼
前端轮询任务进度 → 完成后下载报告
```

### 6.2 多模态检索流程
```
请求（图片/文本/条码/混合）
   │
   ▼
条码检索分支 → MySQL 精确匹配（最快路径）
   │
   ▼（无条码或未命中）
图像/文本向量分支：
   ├─ CLIP 提图像向量 / BGE 提文本向量
   ├─ Milvus 检索 TopN（含距离分数）
   └─ 混合检索：图像分数 * w_img + 文本分数 * w_text
   │
   ▼
阈值过滤（相似度 < threshold 丢弃）
   │
   ▼
按 barcode 回查 MySQL 元数据
   │
   ▼
返回 TopN 候选商品列表
```

### 6.3 事务与回滚策略
- **atomic 模式**：整批写入 MySQL 使用单事务，任一条失败 → 全部 ROLLBACK，向量库不写入
- **partial 模式**：逐条 try-commit，失败条目记录到 fail_detail，最后导出 CSV 供修正重跑
- **向量库一致性**：MySQL 提交成功后才写 Milvus；删除商品时同步删除 Milvus 向量

### 6.4 权限模型
| 角色 | 检索 | 商品CRUD | 批量导入 | 任务管理 | 用户管理 |
|------|------|----------|----------|----------|----------|
| staff 店员 | ✅ | ❌ | ❌ | ❌ | ❌ |
| operator 运营 | ✅ | ✅ | ✅ | ✅ | ❌ |
| admin 管理员 | ✅ | ✅ | ✅ | ✅ | ✅ |

### 6.5 二期预留接口（本期不实现，仅留接口签名）
- OCR 识别包装文字辅助检索 → `POST /api/search/ocr`（预留）
- ERP 库存实时同步 → `POST /api/goods/sync-stock`（预留）
- 检索日志统计 → `GET /api/stats/search-log`（预留）
- 同类商品推荐 → `GET /api/goods/{barcode}/recommend`（预留）

---

## 七、API 接口规划

### 7.1 检索接口
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/search/image | 图片检索（multipart） |
| POST | /api/search/text | 文本检索 |
| GET  | /api/search/barcode/{barcode} | 条码精确检索 |
| POST | /api/search/hybrid | 图文混合检索 |
| POST | /api/search/ocr | OCR 检索（二期预留） |

### 7.2 批量导入接口
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/import/upload | 上传 Excel + 图片zip，创建异步任务 |
| POST | /api/import/push | API 批量推送 JSON（方案B） |
| GET  | /api/import/tasks | 任务列表 |
| GET  | /api/import/tasks/{task_id} | 任务详情/进度 |
| GET  | /api/import/tasks/{task_id}/report | 下载导入报告 |

### 7.3 商品管理接口
| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | /api/goods | 商品分页列表 |
| GET  | /api/goods/{barcode} | 商品详情 |
| PUT  | /api/goods/{barcode} | 编辑商品 |
| DELETE | /api/goods/{barcode} | 删除商品 |

### 7.4 鉴权接口
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/login | 登录获取 JWT |

---

## 八、非功能保障措施

| 需求 | 措施 |
|------|------|
| 上千条导入不阻塞 | 全部走 Celery 异步任务，接口立即返回 task_id |
| 检索响应 < 500ms | Milvus 索引（IVF/HNSW）+ Redis 缓存热点商品 |
| 失败不污染数据库 | atomic 单事务回滚；partial 逐条独立事务 |
| 模块化、可扩展 | service 层拆分，二期接口预留签名 |
| 中文注释 | 所有模块文件加中文注释 |

---

## 九、交付物清单

| # | 交付物 | 状态 |
|---|--------|------|
| 1 | plan.md 项目规划文档 | ✅ 本文档 |
| 2 | 完整项目源代码（后端 + 前端） | ⏳ 待生成 |
| 3 | MySQL 建表 SQL 脚本（init.sql） | ⏳ 待生成 |
| 4 | API 接口文档（检索 + 批量导入） | ⏳ 含于代码注释 + run_guide |
| 5 | env_setup.txt 环境搭建文档 | ⏳ 待生成 |
| 6 | run_guide.txt 项目运行操作手册 | ⏳ 待生成 |
| 7 | Excel 批量导入模板（goods_import_template.xlsx） | ⏳ 待生成 |
| 8 | 测试脚本（批量导入 + 多模态检索） | ⏳ 待生成 |

---

## 十、执行顺序

> 用户已明确要求：**优先生成完整代码，再输出 env_setup.txt，最后输出 run_guide.txt**

1. ✅ 输出 plan.md（本文档）→ **等待用户确认**
2. 🔨 阶段 1-5：生成完整项目代码（后端 + 前端 + SQL + 模板 + 测试脚本）
3. 📄 生成 env_setup.txt
4. 📄 生成 run_guide.txt
5. ✅ 交付完成
