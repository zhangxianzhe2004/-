<template>
  <div class="camera-page">
    <el-row :gutter="20">
      <!-- 左侧：摄像头区域 -->
      <el-col :span="14">
        <el-card shadow="never" class="camera-card">
          <template #header>
            <div class="card-header">
              <span>📷 摄像头实时画面</span>
              <el-switch
                v-model="autoMode"
                active-text="自动识别"
                :disabled="!cameraOn"
                @change="handleAutoModeChange"
              />
            </div>
          </template>

          <!-- 视频显示区 -->
          <div class="video-wrap">
            <video
              v-show="cameraOn"
              ref="videoRef"
              autoplay
              playsinline
              muted
              class="video"
            ></video>
            <!-- 拍照成功闪光效果 -->
            <div v-if="flash" class="flash"></div>
            <!-- 扫描线动画（自动识别时显示） -->
            <div v-if="cameraOn && autoMode" class="scan-line"></div>

            <!-- 未开启摄像头时的占位 -->
            <div v-if="!cameraOn" class="video-placeholder">
              <el-icon :size="64" color="#c8b8a8"><Camera /></el-icon>
              <p>{{ cameraTip }}</p>
              <el-button type="primary" round @click="openCamera">打开摄像头</el-button>
            </div>

            <!-- 识别中遮罩角标 -->
            <div v-if="cameraOn && recognizing" class="recognizing-badge">
              <el-icon class="is-loading"><Loading /></el-icon> 识别中...
            </div>
          </div>

          <!-- 控制按钮 -->
          <div class="controls" v-if="cameraOn">
            <el-select v-model="deviceId" placeholder="选择摄像头" style="width: 220px" @change="switchCamera">
              <el-option
                v-for="d in deviceList"
                :key="d.deviceId"
                :label="d.label || '摄像头 ' + (d.index + 1)"
                :value="d.deviceId"
              />
            </el-select>
            <el-button type="primary" size="large" round :loading="recognizing" @click="captureAndSearch">
              <el-icon><Camera /></el-icon>&nbsp;拍照识别
            </el-button>
            <el-button size="large" round @click="closeCamera">关闭摄像头</el-button>
          </div>

          <!-- 自动识别间隔设置 -->
          <div class="auto-setting" v-if="cameraOn && autoMode">
            <span>自动识别间隔：</span>
            <el-radio-group v-model="autoInterval" size="small" @change="restartTimer">
              <el-radio-button :value="2000">2 秒</el-radio-button>
              <el-radio-button :value="3000">3 秒</el-radio-button>
              <el-radio-button :value="5000">5 秒</el-radio-button>
            </el-radio-group>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：识别结果 -->
      <el-col :span="10">
        <el-card shadow="never" class="result-card">
          <template #header>
            <div class="card-header">
              <span>🔍 识别结果</span>
              <el-tag v-if="lastCaptureUrl" size="small" type="info">基于最近一次拍照</el-tag>
            </div>
          </template>

          <div v-if="!results.length" class="empty-result">
            <el-empty description="暂无识别结果，请拍照或开启自动识别" :image-size="80" />
          </div>

          <template v-else>
            <div class="result-summary">
              共 {{ results.length }} 个候选商品 · 耗时 {{ costMs }}ms · 相似度阈值 {{ threshold }}
            </div>
            <div
              v-for="(item, idx) in results"
              :key="item.barcode"
              class="result-item"
              :class="{ 'top-item': idx === 0 }"
            >
              <div class="rank" :class="'rank-' + (idx + 1)">{{ idx + 1 }}</div>
              <img :src="item.image_url" class="goods-img" @error="onImgError" />
              <div class="goods-info">
                <div class="goods-name">{{ item.goods_name }}</div>
                <div class="goods-meta">
                  {{ item.barcode }} · {{ item.category }} · {{ item.spec }}
                </div>
                <div class="goods-meta">
                  ¥{{ item.retail_price }} · 货架 {{ item.shelf_no || '-' }} · 库存 {{ item.stock ?? '-' }}
                </div>
                <el-progress
                  :percentage="Math.round(item.score * 100)"
                  :color="scoreColor(item.score)"
                  :stroke-width="10"
                />
              </div>
            </div>
          </template>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
/** 摄像头识别商品页面
 *
 * 工作原理：
 * 1. 浏览器 getUserMedia API 打开摄像头，<video> 实时预览
 * 2. 拍照时把视频当前帧绘制到 canvas 截图，转成图片文件
 * 3. 复用后端已有的图片检索接口 /api/search/image 完成识别
 * 4. 自动识别模式：定时截帧识别，识别中防重入
 */
import { ref, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../api'

const videoRef = ref(null)
const cameraOn = ref(false)
const cameraTip = ref('点击下方按钮开启摄像头')
const recognizing = ref(false)   // 是否正在识别（防重入）
const flash = ref(false)         // 拍照闪光动画
const autoMode = ref(false)      // 自动识别开关
const autoInterval = ref(3000)   // 自动识别间隔 ms
const deviceList = ref([])       // 可用摄像头列表
const deviceId = ref('')         // 当前选中的摄像头
const results = ref([])          // 检索结果
const costMs = ref(0)            // 检索耗时
const threshold = ref(0.5)       // 相似度阈值（与后端默认一致）
const lastCaptureUrl = ref('')   // 最近一次拍照预览

let stream = null                // 摄像头媒体流
let timer = null                 // 自动识别定时器

// ---------- 摄像头控制 ----------
async function openCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'environment' },
      audio: false,
    })
    videoRef.value.srcObject = stream
    cameraOn.value = true
    cameraTip.value = ''
    // 枚举摄像头设备（必须在授权后才能拿到 label）
    await listDevices()
    if (autoMode.value) startTimer()
  } catch (err) {
    cameraTip.value = '无法访问摄像头'
    if (err.name === 'NotAllowedError') {
      ElMessage.error('摄像头权限被拒绝，请在浏览器地址栏允许摄像头访问')
    } else if (err.name === 'NotFoundError') {
      ElMessage.error('未检测到摄像头设备')
    } else {
      ElMessage.error('打开摄像头失败：' + err.message)
    }
  }
}

// 列出所有摄像头设备
async function listDevices() {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices()
    deviceList.value = devices
      .filter((d) => d.kind === 'videoinput')
      .map((d, i) => ({ ...d, index: i }))
    // 默认选中第一个
    if (!deviceId.value && deviceList.value.length) {
      deviceId.value = deviceList.value[0].deviceId
    }
  } catch (e) {
    console.warn('枚举摄像头失败', e)
  }
}

// 切换摄像头
async function switchCamera() {
  if (!deviceId.value) return
  closeCamera()
  await openCamera()
}

// 关闭摄像头并释放资源
function closeCamera() {
  stopTimer()
  if (stream) {
    stream.getTracks().forEach((t) => t.stop())
    stream = null
  }
  cameraOn.value = false
  autoMode.value = false
}

// ---------- 截帧与识别 ----------
// 把视频当前帧截取为 JPEG Blob
function captureFrame() {
  const video = videoRef.value
  if (!video || !video.videoWidth) return null
  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.92))
}

// 拍照并检索（手动按钮 + 自动模式共用）
async function captureAndSearch() {
  if (recognizing.value) return   // 防重入：上一帧还没识别完就跳过
  const blob = await captureFrame()
  if (!blob) {
    ElMessage.warning('画面未就绪，请稍候')
    return
  }
  recognizing.value = true
  flash.value = true
  setTimeout(() => (flash.value = false), 200)
  try {
    const form = new FormData()
    form.append('file', blob, 'camera.jpg')
    form.append('top_n', 5)
    form.append('threshold', threshold.value)
    const res = await request.post('/search/image', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 15000,
    })
    results.value = res.items || []
    costMs.value = res.cost_ms ?? 0
    lastCaptureUrl.value = URL.createObjectURL(blob)
    if (autoMode.value && results.value.length === 0) {
      // 自动模式下无结果不打扰用户，仅静默
    } else if (!autoMode.value && results.value.length === 0) {
      ElMessage.info('未识别到相似商品，可尝试调整拍摄角度或降低阈值')
    }
  } catch (e) {
    ElMessage.error('识别失败：' + e.message)
  } finally {
    recognizing.value = false
  }
}

// ---------- 自动识别模式 ----------
function handleAutoModeChange(val) {
  val ? startTimer() : stopTimer()
}
function startTimer() {
  stopTimer()
  timer = setInterval(() => {
    if (cameraOn.value && !recognizing.value) captureAndSearch()
  }, autoInterval.value)
}
function restartTimer() {
  if (autoMode.value && cameraOn.value) startTimer()
}
function stopTimer() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

// ---------- 结果展示 ----------
function scoreColor(score) {
  if (score >= 0.8) return '#67c23a'
  if (score >= 0.6) return '#e8733a'
  return '#c0c4cc'
}
function onImgError(e) {
  e.target.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="%23f0e6dc"/></svg>'
}

// 页面离开时务必释放摄像头
onUnmounted(() => {
  stopTimer()
  if (stream) stream.getTracks().forEach((t) => t.stop())
})
</script>

<style scoped>
.camera-page {
  max-width: 1280px;
  margin: 0 auto;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 700;
  color: #3d2f28;
}
.video-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;
  background: #2a201b;
  border-radius: 12px;
  overflow: hidden;
}
.video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.video-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  color: #a89888;
  background: linear-gradient(160deg, #3d2f28, #2a201b);
}
.flash {
  position: absolute;
  inset: 0;
  background: #fff;
  animation: flash-anim 0.2s ease-out;
  pointer-events: none;
}
@keyframes flash-anim {
  from { opacity: 0.8; }
  to { opacity: 0; }
}
/* 自动识别时的扫描线动画 */
.scan-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, #67e0a0, transparent);
  box-shadow: 0 0 12px #67e0a0;
  animation: scan 2.4s ease-in-out infinite;
  pointer-events: none;
}
@keyframes scan {
  0%, 100% { top: 8%; }
  50% { top: 90%; }
}
.recognizing-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.controls {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.auto-setting {
  margin-top: 14px;
  color: #6b5d4f;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.result-card {
  min-height: 420px;
}
.empty-result {
  padding-top: 40px;
}
.result-summary {
  color: #6b5d4f;
  font-size: 13px;
  margin-bottom: 12px;
}
.result-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #f0e6dc;
  margin-bottom: 10px;
  transition: box-shadow 0.2s;
}
.result-item:hover {
  box-shadow: 0 4px 14px rgba(232, 115, 58, 0.12);
}
.result-item.top-item {
  border-color: #f0c0a0;
  background: #fdf8f3;
}
.rank {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #e8e0d8;
  color: #6b5d4f;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  align-self: flex-start;
}
.rank-1 { background: #e8733a; color: #fff; }
.rank-2 { background: #f0a060; color: #fff; }
.rank-3 { background: #f0c090; color: #fff; }
.goods-img {
  width: 72px;
  height: 72px;
  object-fit: cover;
  border-radius: 10px;
  background: #f5efe8;
  flex-shrink: 0;
}
.goods-info {
  flex: 1;
  min-width: 0;
}
.goods-name {
  font-weight: 700;
  color: #3d2f28;
  margin-bottom: 4px;
}
.goods-meta {
  color: #8a7a6a;
  font-size: 12px;
  margin-bottom: 4px;
}
</style>
