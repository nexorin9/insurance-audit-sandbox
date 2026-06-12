import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: auto-add headers
apiClient.interceptors.request.use(
  (config) => {
    config.headers['Content-Type'] = 'application/json'
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: unified 4xx/5xx error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (!error.response) {
      console.error('网络连接失败，请检查服务是否启动')
      return Promise.reject(new Error('网络连接失败，请检查服务是否启动'))
    }
    const status = error.response.status
    let message = `请求失败 (${status})`
    if (status === 400) message = '请求参数错误'
    else if (status === 401) message = '未授权，请检查 API Key'
    else if (status === 403) message = '无权限访问'
    else if (status === 404) message = '请求的资源不存在'
    else if (status >= 500) message = '服务器错误，请稍后重试'
    console.error(message)
    return Promise.reject(new Error(message))
  }
)

export interface RuleSet {
  rule_set_id: string
  name: string
  version: string
  rule_count: number
}

export interface SandboxRun {
  run_id: string
  timestamp: string
  rule_set_id: string
  rule_set_name: string
  total_items: number
  hit_count: number
  high_risk_count: number
  status: string
}

export interface FeeItem {
  item_id: string
  category: string
  amount: number
  unit_price?: number
  quantity?: number
  material_markup_rate?: number
  injection_type?: string
  days_admitted?: number
  procedure_code?: string
}

export const getRules = async (): Promise<RuleSet[]> => {
  const res = await apiClient.get('/rules')
  return res.data
}

export const validateRuleYaml = async (yamlContent: string) => {
  const res = await apiClient.post('/rules/validate', { yaml_content: yamlContent })
  return res.data
}

export const runSandbox = async (ruleSetId: string, feeItems: FeeItem[]) => {
  const res = await apiClient.post('/sandbox/run', { rule_set_id: ruleSetId, fee_items: feeItems })
  return res.data
}

export const getSandboxRuns = async (page = 1, pageSize = 10) => {
  const res = await apiClient.get('/sandbox/runs', { params: { page, page_size: pageSize } })
  return res.data
}

export const getSandboxRun = async (runId: string) => {
  const res = await apiClient.get(`/sandbox/run/${runId}`)
  return res.data
}

export const generateReport = async (runId: string, format: 'pdf' | 'docx' = 'pdf') => {
  const res = await apiClient.post('/reports/generate', { run_id: runId, format }, { responseType: 'blob' })
  return res.data
}

// Rule set version management (Task 26)
export const getRuleSetDetails = async (ruleSetId: string) => {
  const res = await apiClient.get(`/rules/${ruleSetId}`)
  return res.data
}

export const importRuleSet = async (yamlContent: string) => {
  const res = await apiClient.post('/rules/import', { yaml_content: yamlContent })
  return res.data
}

export const exportRuleSet = async (ruleSetId: string) => {
  const res = await apiClient.get(`/rules/${ruleSetId}/export`)
  return res.data
}

export const compareRuleSetVersions = async (ruleSetId: string, compareVersion: string) => {
  const res = await apiClient.get(`/rules/${ruleSetId}/diff`, { params: { compare_version: compareVersion } })
  return res.data
}

// Conflict detection (Task 27)
export const getSandboxRunConflicts = async (runId: string) => {
  const res = await apiClient.get(`/sandbox/run/${runId}/conflicts`)
  return res.data
}

// History comparison (Task 28)
export const compareSandboxRuns = async (runIdA: string, runIdB: string) => {
  const res = await apiClient.get('/sandbox/compare', { params: { run_id_a: runIdA, run_id_b: runIdB } })
  return res.data
}

// Config query
export const getConfig = async () => {
  const res = await apiClient.get('/config')
  return res.data
}

export default apiClient