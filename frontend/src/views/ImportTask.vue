<template>
  <div class="import-page">
    <el-card class="import-card">
      <template #header>
        <div class="card-header">
          <el-icon style="font-size:20px"><Upload /></el-icon>
          <span>批量导入商品（方案A：文件导入）</span>
        </div>
      </template>
      <el-form label-width="140px" class="import-form">
        <el-form-item label="任务名称">
          <el-input v-model="form.task_name" placeholder="可选，便于识别" />
        </el-form-item>
        <el-form-item label="商品清单 Excel/CSV">
          <el-upload
            :auto-upload="false"
            :on-change="(file) => (excelFile = file.raw)"
            accept=".xlsx,.xls,.csv"
          >
            <el-button type="primary">
              <el-icon style="margin-right:4px"><Document /></el-icon>选择 Excel/CSV 文件
            </el-button>
            <template #tip>
              <div class="tip-text">文件须包含字段：barcode, goods_name, category, spec, retail_price（必填）</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="商品图片压缩包">
          <el-upload
            :auto-upload="false"
            :on-change="(file) => (zipFile = file.raw)"
            accept=".zip"
          >
            <el-button type="primary">
              <el-icon style="margin-right:4px"><Picture /></el-icon>选择图片 zip 包
            </el-button>
            <template #tip>
              <div class="tip-text">图片命名规则：{商品条码}.jpg，系统自动按条码匹配</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="条码冲突策略">
          <el-radio-group v-model="form.conflict_strategy">
            <el-radio-button value="skip">跳过</el-radio-button>
            <el-radio-button value="overwrite">覆盖旧数据</el-radio-button>
            <el-radio-button value="abort">整批终止</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="事务模式">
          <el-radio-group v-model="form.transaction_mode">
            <el-radio-button value="atomic">整批原子（失败全部回滚）</el-radio-button>
            <el-radio-button value="partial">部分成功（失败条目导出修正）</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="handleSubmit" size="large">
            <el-icon style="margin-right:4px"><Upload /></el-icon>提交导入任务
          </el-button>
          <el-button @click="downloadTemplate" size="large">
            <el-icon style="margin-right:4px"><Download /></el-icon>下载 Excel 模板
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 提交结果 -->
    <el-card v-if="submitResult" class="result-card">
      <template #header>
        <div class="card-header">
          <el-icon><CircleCheck /></el-icon>
          <span>提交结果</span>
        </div>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="任务ID">{{ submitResult.task_id }}</el-descriptions-item>
        <el-descriptions-item label="总条数">{{ submitResult.total }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ submitResult.message }}</el-descriptions-item>
      </el-descriptions>
      <el-button type="primary" @click="$router.push('/tasks')" style="margin-top: 12px">
        <el-icon style="margin-right:4px"><List /></el-icon>查看任务进度
      </el-button>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const form = reactive({
  task_name: '',
  conflict_strategy: 'skip',
  transaction_mode: 'partial',
})
const excelFile = ref(null)
const zipFile = ref(null)
const submitting = ref(false)
const submitResult = ref(null)

async function handleSubmit() {
  if (!excelFile.value) {
    ElMessage.warning('请选择 Excel/CSV 商品清单')
    return
  }
  submitting.value = true
  try {
    const fd = new FormData()
    fd.append('excel_file', excelFile.value)
    if (zipFile.value) fd.append('image_zip', zipFile.value)
    fd.append('conflict_strategy', form.conflict_strategy)
    fd.append('transaction_mode', form.transaction_mode)
    if (form.task_name) fd.append('task_name', form.task_name)
    const res = await api.post('/import/upload', fd)
    submitResult.value = res
    ElMessage.success('任务已提交，正在异步处理')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitting.value = false
  }
}

// 下载 Excel 导入模板（从后端获取）
async function downloadTemplate() {
  window.open('/api/import/template', '_blank')
}
</script>

<style scoped>
.import-page { padding: 20px; }
.import-card, .result-card {
  border-radius: 12px;
}
.import-card { margin-bottom: 16px; }
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 700;
  color: #3d2f28;
}
.import-form { padding: 12px 8px 0; }
.tip-text {
  color: #b0a090;
  font-size: 12px;
  padding-top: 4px;
}
</style>
