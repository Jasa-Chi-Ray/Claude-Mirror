<template>
  <div>
    <t-card title="Claude 上游账号" subtitle="维护 Claude 网页会话凭证与诊断状态" :bordered="false">
      <template #actions>
        <t-space>
          <AccountHealthSettings />
          <t-button :loading="checkingAll" @click="handleCheckTokenExpiry()">
            <template #icon><t-icon name="search" /></template>
            一键检测
          </t-button>
          <t-button theme="primary" @click="showAddDialog">
            <template #icon><t-icon name="add" /></template>
            添加账号
          </t-button>
        </t-space>
      </template>
      <div class="account-toolbar">
        <t-input v-model="query" clearable placeholder="搜索上游账号" @enter="applyFilters" />
        <t-select v-model="statusFilter" clearable placeholder="全部状态" @change="applyFilters">
          <t-option value="healthy" label="健康" />
          <t-option value="unhealthy" label="异常" />
        </t-select>
        <t-button variant="outline" @click="applyFilters">查询</t-button>
      </div>

      <t-table
        :data="tableData"
        :columns="columns"
        :loading="loading"
        :pagination="pagination"
        @page-change="onPageChange"
        row-key="id"
      >
        <template #auth_status="{ row }">
          <t-tag :theme="row.auth_status ? 'success' : 'danger'">
            {{ row.auth_status ? '有效' : '已过期' }}
          </t-tag>
        </template>
        <template #plan_type="{ row }">
          <t-tag :theme="getPlanTheme(row.plan_type)">
            {{ row.plan_type }}
          </t-tag>
        </template>
        <template #login_count="{ row }">
          <span>{{ row.login_count || 0 }} 次</span>
        </template>
        <template #session_token_valid="{ row }">
          <t-tag :theme="row.auth_state === 'unknown' ? 'warning' : (row.session_token_valid ? 'success' : 'danger')">
            {{ row.auth_state === 'unknown' ? '暂不可验证' : (row.session_token_valid ? '可用' : '不可用') }}
          </t-tag>
        </template>
        <template #supported_login_modes="{ row }">
          <span>{{ row.supported_login_modes?.length ? 'Claude 网页' : '无' }}</span>
        </template>
        <template #last_check_at="{ row }">
          <span>{{ formatCheckTime(row.last_check_at) }}</span>
        </template>
        <template #proxy_node_id="{ row }">
          <t-tag :theme="row.proxy_node_id ? 'primary' : 'default'" variant="light">
            {{ row.proxy_node_id ? `节点 ${row.proxy_node_id}` : '直连' }}
          </t-tag>
        </template>
        <template #token_remaining="{ row }">
          <t-tag :theme="getTokenRemainingTheme(row)" variant="light">
            {{ formatTokenRemaining(row) }}
          </t-tag>
        </template>
        <template #last_error="{ row }">
          <span>{{ row.last_error || '-' }}</span>
        </template>
        <template #op="{ row }">
          <t-space>
            <t-link theme="primary" :loading="checkingId === row.id" @click="handleCheckTokenExpiry(row)">
              检测
            </t-link>
            <t-link theme="primary" @click="showEditDialog(row)">编辑</t-link>
            <t-popconfirm content="确定重置该账号的被登录次数吗？" @confirm="handleResetLoginCount(row)">
              <t-link theme="warning">重置次数</t-link>
            </t-popconfirm>
            <t-popconfirm content="确定删除该账号吗？" @confirm="handleDelete(row)">
              <t-link theme="danger">删除</t-link>
            </t-popconfirm>
          </t-space>
        </template>
      </t-table>
    </t-card>

    <!-- 添加对话框 -->
    <t-dialog
      :visible="addDialogVisible"
      header="添加上游账号"
      :confirm-btn="{ loading: submitLoading }"
      @confirm="handleAdd"
      @close="addDialogVisible = false"
      width="600px"
    >
      <t-form :data="addFormData" ref="addFormRef" label-width="120px">
        <t-form-item label="会话凭据列表" name="chatgpt_token_list">
          <t-textarea
            v-model="tokenInput"
            placeholder="支持 sessionKey（sk-ant-sid01-* / sk-ant-sid02-*）、完整 Cookie 文本、Netscape 或 JSON Cookie"
            :autosize="{ minRows: 5, maxRows: 10 }"
          />
        </t-form-item>
        <t-form-item label="代理节点" name="proxy_node_id">
          <t-select v-model="addFormData.proxy_node_id" :clearable="!proxyRequired" :placeholder="proxyRequired ? '必须选择启用的代理节点' : '不绑定节点则使用服务器出口'">
            <t-option
              v-for="node in proxyNodeOptions"
              :key="node.id"
              :value="node.id"
              :label="node.label"
            />
          </t-select>
        </t-form-item>
        <t-form-item>
          <t-alert theme="info" message="仅用于 Claude 网页会话：支持 sessionKey、浏览器 Cookie 文本、Netscape 与 JSON Cookie，并自动保留所需 Cookie。" />
        </t-form-item>
      </t-form>
    </t-dialog>

    <!-- 编辑对话框 -->
    <t-dialog
      :visible="editDialogVisible"
      header="编辑账号备注"
      :confirm-btn="{ loading: submitLoading }"
      @confirm="handleEdit"
      @close="editDialogVisible = false"
    >
      <t-form :data="editFormData" ref="editFormRef" label-width="100px">
        <t-form-item label="账号">
          <t-input :value="editFormData.chatgpt_username" disabled />
        </t-form-item>
        <t-form-item label="备注" name="remark">
          <t-textarea v-model="editFormData.remark" placeholder="请输入备注" />
        </t-form-item>
        <t-form-item label="代理节点" name="proxy_node_id">
          <t-select v-model="editFormData.proxy_node_id" :clearable="!proxyRequired" :placeholder="proxyRequired ? '必须选择启用的代理节点' : '不绑定节点则直连'">
            <t-option
              v-for="node in proxyNodeOptions"
              :key="node.id"
              :value="node.id"
              :label="node.label"
            />
          </t-select>
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import request from '@/api/request'
import AccountHealthSettings from './components/AccountHealthSettings.vue'

const loading = ref(false)
const submitLoading = ref(false)
const addDialogVisible = ref(false)
const editDialogVisible = ref(false)
const addFormRef = ref()
const editFormRef = ref()
const tableData = ref<any[]>([])
const tokenInput = ref('')
const proxyNodeOptions = ref<Array<{ id: number, label: string }>>([])
const proxyRequired = ref(false)
const checkingAll = ref(false)
const checkingId = ref<number | null>(null)
const query = ref('')
const statusFilter = ref('')

const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0
})

const columns = [
  { colKey: 'id', title: 'ID', width: 80 },
  { colKey: 'chatgpt_username', title: '账号', ellipsis: true },
  { colKey: 'plan_type', title: '套餐', cell: 'plan_type', width: 100 },
  { colKey: 'auth_status', title: '状态', cell: 'auth_status', width: 100 },
  { colKey: 'session_token_valid', title: 'Claude 网页会话', cell: 'session_token_valid', width: 140 },
  { colKey: 'supported_login_modes', title: '支持入口', cell: 'supported_login_modes', width: 160 },
  { colKey: 'login_count', title: '被登录次数', cell: 'login_count', width: 120 },
  { colKey: 'proxy_node_id', title: '代理节点', cell: 'proxy_node_id', width: 110 },
  { colKey: 'token_remaining', title: '会话到期', cell: 'token_remaining', width: 150 },
  { colKey: 'last_check_at', title: '最近诊断', cell: 'last_check_at', width: 160 },
  { colKey: 'last_error', title: '诊断结果', cell: 'last_error', ellipsis: true },
  { colKey: 'remark', title: '备注', ellipsis: true },
  { colKey: 'op', title: '操作', cell: 'op', width: 260 }
]

const addFormData = reactive({
  chatgpt_token_list: [] as string[],
  proxy_node_id: null as number | null
})

const editFormData = reactive({
  chatgpt_username: '',
  remark: '',
  proxy_node_id: null as number | null
})

onMounted(() => {
  fetchData()
  fetchProxyNodes()
})

const formatCheckTime = (value?: number | null) => {
  if (!value) return '-'
  const date = new Date(value * 1000)
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mi = String(date.getMinutes()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}`
}

const getPlanTheme = (planType?: string) => {
  const normalized = (planType || '').toLowerCase()
  if (['team', 'business', 'enterprise', 'workspace'].includes(normalized)) {
    return 'warning'
  }
  if (['plus', 'pro'].includes(normalized)) {
    return 'primary'
  }
  return 'default'
}

const formatTokenRemaining = (row: any) => {
  return row?.expiry_status === 'unknown' ? '未知（以诊断为准）' : '-'
}

const getTokenRemainingTheme = (row: any) => {
  return row?.session_token_valid ? 'success' : 'danger'
}

const fetchData = async () => {
  loading.value = true
  const params = new URLSearchParams({
    page: String(pagination.current),
    page_size: String(pagination.pageSize)
  })
  if (query.value.trim()) params.set('q', query.value.trim())
  if (statusFilter.value) params.set('status', statusFilter.value)
  const data = await request(`/0x/claude?${params.toString()}`)
  loading.value = false
  
  if (data) {
    tableData.value = data.results || []
    pagination.total = data.count || 0
  }
}

const applyFilters = () => {
  pagination.current = 1
  fetchData()
}

const fetchProxyNodes = async () => {
  const data = await request('/0x/user/proxy-node-options')
  if (data) {
    proxyRequired.value = data.require_proxy === true
    proxyNodeOptions.value = (data.nodes || [])
      .map((node: any) => ({ id: Number(node.id), label: String(node.label || `节点 ${node.id}`) }))
      .filter((node: any) => node.id > 0)
  }
}

const onPageChange = (pageInfo: any) => {
  pagination.current = pageInfo.current
  pagination.pageSize = pageInfo.pageSize
  fetchData()
}

const showAddDialog = () => {
  tokenInput.value = ''
  addFormData.proxy_node_id = null
  addDialogVisible.value = true
}

const showEditDialog = (row: any) => {
  editFormData.chatgpt_username = row.chatgpt_username
  editFormData.remark = row.remark || ''
  editFormData.proxy_node_id = row.proxy_node_id || null
  editDialogVisible.value = true
}

const looksLikeNetscapeCookieFile = (raw: string) => {
  if (raw.includes('# Netscape HTTP Cookie File')) {
    return true
  }
  return raw
    .split('\n')
    .map(line => line.trim())
    .filter(line => line && !line.startsWith('#'))
    .some(line => line.split('\t').length >= 7)
}

const looksLikeJsonCookiePayload = (raw: string) => {
  if (!/^[{[]/.test(raw)) return false
  try {
    const value = JSON.parse(raw)
    return Array.isArray(value) || (typeof value === 'object' && value !== null)
  } catch {
    return false
  }
}

const splitTokenInputs = (raw: string) => {
  const trimmed = raw.trim()
  if (!trimmed) {
    return []
  }
  if (looksLikeNetscapeCookieFile(trimmed) || looksLikeJsonCookiePayload(trimmed)) {
    return [trimmed]
  }
  return trimmed
    .split('\n')
    .map(item => item.trim())
    .filter(Boolean)
}

const handleAdd = async () => {
  const tokens = splitTokenInputs(tokenInput.value)
  if (tokens.length === 0) {
    MessagePlugin.warning('请输入至少一个 sessionKey 或 Cookie')
    return
  }
  if (proxyRequired.value && !addFormData.proxy_node_id) {
    MessagePlugin.warning('当前服务要求选择启用的代理节点')
    return
  }

  submitLoading.value = true
  const data = await request('/0x/claude', 'POST', {
    chatgpt_token_list: tokens,
    proxy_node_id: addFormData.proxy_node_id || null
  })
  submitLoading.value = false

  if (data) {
    if (data.errors?.length) {
      MessagePlugin.warning(data.message || `部分添加成功，失败 ${data.errors.length} 个`)
    } else {
      MessagePlugin.success(data.message || '添加成功')
    }
    addDialogVisible.value = false
    fetchData()
  }
}

const handleEdit = async () => {
  if (proxyRequired.value && !editFormData.proxy_node_id) {
    MessagePlugin.warning('当前服务要求选择启用的代理节点')
    return
  }
  submitLoading.value = true
  const data = await request('/0x/claude', 'PUT', {
    ...editFormData,
    proxy_node_id: editFormData.proxy_node_id || null
  })
  submitLoading.value = false

  if (data) {
    MessagePlugin.success('更新成功')
    editDialogVisible.value = false
    fetchData()
  }
}

const mergeTokenCheckResults = (results: any[]) => {
  const resultMap = new Map(results.map(item => [item.id, item]))
  tableData.value = tableData.value.map(row => {
    const result = resultMap.get(row.id)
    return result ? { ...row, ...result } : row
  })
}

const summarizeTokenCheck = (results: any[]) => {
  if (results.length === 0) return '没有可检测的账号'
  if (results.length === 1) {
    if (results[0].auth_state === 'unknown') return '诊断完成：Claude 网页会话暂不可验证'
    return `诊断完成：${results[0].session_token_valid ? 'Claude 网页会话可用' : 'Claude 网页会话不可用'}`
  }
  const unavailableCount = results.filter(item => item.auth_state !== 'unknown' && !item.session_token_valid).length
  const unknownCount = results.filter(item => item.auth_state === 'unknown').length
  return `诊断完成：${results.length}个账号，网页会话不可用 ${unavailableCount} 个，暂不可验证 ${unknownCount} 个`
}

const handleCheckTokenExpiry = async (row?: any) => {
  const ids = row ? [row.id] : tableData.value.map(item => item.id)
  if (ids.length === 0) {
    MessagePlugin.warning('当前页没有账号')
    return
  }

  if (row) {
    checkingId.value = row.id
  } else {
    checkingAll.value = true
  }

  const data = await request('/0x/claude/token-expiry', 'POST', row ? { ids } : {})

  if (row) {
    checkingId.value = null
  } else {
    checkingAll.value = false
  }

  if (data?.results) {
    mergeTokenCheckResults(data.results)
    MessagePlugin.success(summarizeTokenCheck(data.results))
  }
}

const handleDelete = async (row: any) => {
  const data = await request('/0x/claude', 'DELETE', {
    chatgpt_username: row.chatgpt_username
  })
  if (data) {
    MessagePlugin.success('删除成功')
    fetchData()
  }
}

const handleResetLoginCount = async (row: any) => {
  const data = await request('/0x/claude/reset-login-count', 'POST', { id: row.id })
  if (data) {
    row.login_count = 0
    MessagePlugin.success(data.message || '被登录次数已重置')
  }
}
</script>

<style scoped>
.account-toolbar {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) 180px auto;
  gap: 10px;
  margin-bottom: 16px;
}
</style>
