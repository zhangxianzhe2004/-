<template>
  <div class="search-page">
    <el-card class="search-card">
      <el-tabs v-model="activeTab" class="search-tabs">
        <!-- 图片检索 -->
        <el-tab-pane label="📷 图片检索" name="image">
          <div class="tab-inner">
            <el-upload
              drag
              :auto-upload="false"
              :on-change="(file) => (imageFile = file.raw)"
              accept="image/*"
              class="upload-area"
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">拖拽商品照片到此处，或<em>点击上传</em></div>
            </el-upload>
            <div class="search-params">
              <span class="param-label">返回数量</span>
              <el-input-number v-model="topN" :min="1" :max="50" size="small" />
              <span class="param-label">相似度阈值</span>
              <el-input-number v-model="threshold" :min="0" :max="1" :step="0.05" size="small" />
              <el-button type="primary" :loading="loading" @click="doImageSearch">
                <el-icon style="margin-right:4px"><Search /></el-icon>开始检索
              </el-button>
            </div>
          </div>
        </el-tab-pane>

        <!-- 文本检索 -->
        <el-tab-pane label="📝 文本检索" name="text">
          <div class="tab-inner">
            <el-input
              v-model="textQuery"
              type="textarea"
              :rows="3"
              placeholder="输入商品描述，如：红色瓶装可乐"
            />
            <div class="search-params">
              <span class="param-label">返回数量</span>
              <el-input-number v-model="topN" :min="1" :max="50" size="small" />
              <span class="param-label">相似度阈值</span>
              <el-input-number v-model="threshold" :min="0" :max="1" :step="0.05" size="small" />
              <el-button type="primary" :loading="loading" @click="doTextSearch">
                <el-icon style="margin-right:4px"><Search /></el-icon>开始检索
              </el-button>
            </div>
          </div>
        </el-tab-pane>

        <!-- 条码检索 -->
        <el-tab-pane label="📊 条码检索" name="barcode">
          <div class="tab-inner">
            <el-input v-model="barcode" placeholder="输入13位商品条码" @keyup.enter="doBarcodeSearch" size="large" />
            <div class="search-params">
              <el-button type="primary" :loading="loading" @click="doBarcodeSearch" size="large">
                <el-icon style="margin-right:4px"><Search /></el-icon>精确查询
              </el-button>
            </div>
          </div>
        </el-tab-pane>

        <!-- 混合检索 -->
        <el-tab-pane label="🔀 混合检索" name="hybrid">
          <div class="tab-inner">
            <el-input
              v-model="textQuery"
              type="textarea"
              :rows="2"
              placeholder="文本描述（可选）"
            />
            <el-upload
              drag
              :auto-upload="false"
              :on-change="(file) => (imageFile = file.raw)"
              accept="image/*"
              style="margin-top: 12px"
              class="upload-area"
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">商品图片（可选）</div>
            </el-upload>
            <div class="search-params">
              <span class="param-label">图像权重</span>
              <el-input-number v-model="imageWeight" :min="0" :max="1" :step="0.1" size="small" />
              <span class="param-label">文本权重</span>
              <el-input-number v-model="textWeight" :min="0" :max="1" :step="0.1" size="small" />
              <el-button type="primary" :loading="loading" @click="doHybridSearch">
                <el-icon style="margin-right:4px"><Search /></el-icon>混合检索
              </el-button>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 检索结果 -->
    <el-card class="result-card">
      <div class="result-header">
        <el-icon><Document /></el-icon>
        <span>检索结果（{{ resultList.length }} 条，耗时 {{ costMs }}ms）</span>
      </div>
      <el-table :data="resultList" v-if="resultList.length" row-class-name="table-row">
        <el-table-column label="商品图片" width="100">
          <template #default="{ row }">
            <el-image
              v-if="row.image_path"
              :src="getImageUrl(row.image_path)"
              style="width: 72px; height: 72px"
              fit="cover"
              class="goods-thumb"
            />
          </template>
        </el-table-column>
        <el-table-column prop="goods_name" label="商品名称" />
        <el-table-column prop="barcode" label="条码" width="150" />
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column prop="spec" label="规格" width="120" />
        <el-table-column prop="retail_price" label="零售价" width="100">
          <template #default="{ row }">
            <span class="price-text">¥{{ row.retail_price }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="shelf_no" label="货架" width="80" />
        <el-table-column prop="stock" label="库存" width="80" />
        <el-table-column prop="score" label="相似度" width="120">
          <template #default="{ row }">
            <el-progress :percentage="Math.round(row.score * 100)" />
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无结果，请执行检索" />
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const activeTab = ref('image')
const imageFile = ref(null)
const textQuery = ref('')
const barcode = ref('')
const topN = ref(10)
const threshold = ref(0.5)
const imageWeight = ref(0.6)
const textWeight = ref(0.4)
const loading = ref(false)
const resultList = ref([])
const costMs = ref(0)

// 图片检索
async function doImageSearch() {
  if (!imageFile.value) {
    ElMessage.warning('请先上传图片')
    return
  }
  loading.value = true
  try {
    const fd = new FormData()
    fd.append('file', imageFile.value)
    fd.append('top_n', topN.value)
    fd.append('threshold', threshold.value)
    const res = await api.post('/search/image', fd)
    showResult(res)
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

// 文本检索
async function doTextSearch() {
  if (!textQuery.value) {
    ElMessage.warning('请输入文本描述')
    return
  }
  loading.value = true
  try {
    const res = await api.post('/search/text', {
      query: textQuery.value,
      top_n: topN.value,
      threshold: threshold.value,
    })
    showResult(res)
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

// 条码检索
async function doBarcodeSearch() {
  if (!barcode.value) {
    ElMessage.warning('请输入条码')
    return
  }
  loading.value = true
  try {
    const res = await api.get(`/search/barcode/${barcode.value}`)
    showResult(res)
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

// 混合检索
async function doHybridSearch() {
  if (!imageFile.value && !textQuery.value) {
    ElMessage.warning('请至少提供图片或文本')
    return
  }
  loading.value = true
  try {
    const fd = new FormData()
    if (textQuery.value) fd.append('text_query', textQuery.value)
    if (imageFile.value) fd.append('file', imageFile.value)
    fd.append('top_n', topN.value)
    fd.append('threshold', threshold.value)
    fd.append('image_weight', imageWeight.value)
    fd.append('text_weight', textWeight.value)
    const res = await api.post('/search/hybrid', fd)
    showResult(res)
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

function showResult(res) {
  resultList.value = res.items || []
  costMs.value = res.cost_ms || 0
  if (resultList.value.length === 0) {
    ElMessage.info('未检索到符合条件的商品（可能低于相似度阈值）')
  }
}

// 拼接图片 URL：轻量模式走后端 /api/file，完整模式（http 开头）直接使用
function getImageUrl(path) {
  if (!path) return ''
  return path.startsWith('http') ? path : `/api/file/${path}`
}
</script>

<style scoped>
.search-page { padding: 20px; }
.search-card, .result-card {
  border-radius: 12px;
  margin-bottom: 16px;
}
.tab-inner { padding: 12px 0; }
.upload-area {
  border-radius: 10px;
}
.search-params {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.param-label {
  color: #8a7a6a;
  font-size: 14px;
  white-space: nowrap;
}
.result-header {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 12px;
  color: #3d2f28;
  display: flex;
  align-items: center;
  gap: 6px;
}
.goods-thumb {
  border-radius: 8px;
  border: 2px solid #f0e6dc;
}
.price-text {
  color: #e8733a;
  font-weight: 700;
  font-size: 15px;
}
:deep(.table-row:hover > td) {
  background: #faf2ec !important;
}
</style>
