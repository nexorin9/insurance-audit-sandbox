import { useState, useEffect, useCallback, useRef } from 'react'
import { getRules, validateRuleYaml, RuleSet } from '../api/apiClient'

interface RuleEntry {
  rule_id: string
  name: string
  condition: string
  risk_score: number
  category: string
  description?: string
}

interface RuleSetDetail extends RuleSet {
  rules: RuleEntry[]
  description?: string
  updated_at?: string
}

interface ValidationResult {
  valid: boolean
  errors: string[]
  rule_count: number
}

export default function RuleSetManage() {
  const [ruleSets, setRuleSets] = useState<RuleSet[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Detail modal
  const [selectedRuleSet, setSelectedRuleSet] = useState<RuleSetDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)

  // Upload
  const [uploadResult, setUploadResult] = useState<ValidationResult | null>(null)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const fetchRuleSets = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getRules()
      setRuleSets(data)
    } catch (err) {
      setError('加载规则集失败，请检查服务是否启动')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchRuleSets()
  }, [fetchRuleSets])

  const openDetail = async (ruleSet: RuleSet) => {
    setDetailLoading(true)
    setDetailError(null)
    setSelectedRuleSet(null)
    try {
      // GET /rules/{rule_set_id}
      const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
      const res = await fetch(`${baseURL}/rules/${ruleSet.rule_set_id}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: RuleSetDetail = await res.json()
      setSelectedRuleSet(data)
    } catch (err) {
      setDetailError('加载规则集详情失败')
    } finally {
      setDetailLoading(false)
    }
  }

  const closeDetail = () => {
    setSelectedRuleSet(null)
    setDetailError(null)
  }

  const handleFileUpload = async (file: File) => {
    setUploadLoading(true)
    setUploadError(null)
    setUploadResult(null)
    try {
      const text = await file.text()
      const result = await validateRuleYaml(text)
      setUploadResult(result)
    } catch {
      setUploadError('上传失败，请检查服务是否启动')
    } finally {
      setUploadLoading(false)
    }
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file && (file.name.endsWith('.yaml') || file.name.endsWith('.yml'))) {
      handleFileUpload(file)
    } else {
      setUploadError('请上传 .yaml 或 .yml 文件')
    }
  }, [])

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFileUpload(file)
  }

  const resetUpload = () => {
    setUploadResult(null)
    setUploadError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div className="p-8 min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-800">规则集管理</h1>
          <button
            onClick={fetchRuleSets}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition"
          >
            刷新列表
          </button>
        </div>

        {/* Upload Card */}
        <div className="bg-white rounded-lg shadow mb-6 p-6">
          <h2 className="text-lg font-semibold mb-4 text-gray-700">自定义规则上传</h2>
          <div
            className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-400 transition cursor-pointer"
            onDragOver={(e) => e.preventDefault()}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            {uploadLoading ? (
              <div className="text-blue-600">
                <div className="animate-spin inline-block w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full mr-2" />
                验证中...
              </div>
            ) : (
              <>
                <div className="text-3xl mb-2">📤</div>
                <p className="text-gray-600 mb-1">拖拽 YAML 文件到此处，或<span className="text-blue-600 underline">点击选择</span></p>
                <p className="text-xs text-gray-400">支持 .yaml / .yml 格式</p>
              </>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".yaml,.yml"
              className="hidden"
              onChange={onFileChange}
            />
          </div>

          {/* Upload Result */}
          {uploadError && (
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-600 font-medium">上传失败</p>
              <p className="text-red-500 text-sm mt-1">{uploadError}</p>
            </div>
          )}
          {uploadResult && (
            <div className={`mt-4 p-4 rounded-lg border ${uploadResult.valid ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
              <div className="flex items-center justify-between">
                <div>
                  {uploadResult.valid ? (
                    <p className="text-green-700 font-semibold">✅ 验证通过</p>
                  ) : (
                    <p className="text-red-700 font-semibold">❌ 验证失败</p>
                  )}
                  {uploadResult.rule_count > 0 && (
                    <p className={`text-sm mt-1 ${uploadResult.valid ? 'text-green-600' : 'text-red-500'}`}>
                      共 {uploadResult.rule_count} 条规则
                    </p>
                  )}
                </div>
                <button onClick={resetUpload} className="text-sm text-gray-500 hover:text-gray-700 underline">
                  清除
                </button>
              </div>
              {uploadResult.errors.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {uploadResult.errors.map((err, i) => (
                    <li key={i} className="text-red-500 text-sm flex items-start gap-2">
                      <span className="text-red-400 mt-0.5">•</span>
                      <span>{err}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        {/* Rule Set List */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-700">可用规则集</h2>
          </div>

          {loading && (
            <div className="p-8 text-center text-gray-500">
              <div className="animate-spin inline-block w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full mr-2 align-middle" />
              加载中...
            </div>
          )}

          {error && (
            <div className="p-6 text-center">
              <p className="text-red-500">{error}</p>
            </div>
          )}

          {!loading && !error && ruleSets.length === 0 && (
            <div className="p-8 text-center text-gray-400">
              暂无可用规则集，请先上传规则 YAML 文件
            </div>
          )}

          {!loading && !error && ruleSets.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-gray-50 text-gray-600 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 font-semibold">规则集名称</th>
                    <th className="px-6 py-3 font-semibold">ID</th>
                    <th className="px-6 py-3 font-semibold">版本</th>
                    <th className="px-6 py-3 font-semibold text-center">规则条数</th>
                    <th className="px-6 py-3 font-semibold text-center">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {ruleSets.map((rs) => (
                    <tr key={rs.rule_set_id} className="hover:bg-gray-50 transition">
                      <td className="px-6 py-4 font-medium text-gray-800">{rs.name}</td>
                      <td className="px-6 py-4 text-gray-500 font-mono text-xs">{rs.rule_set_id}</td>
                      <td className="px-6 py-4 text-gray-600">{rs.version}</td>
                      <td className="px-6 py-4 text-center">
                        <span className="inline-flex items-center justify-center w-8 h-6 bg-blue-100 text-blue-700 rounded text-xs font-medium">
                          {rs.rule_count}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <button
                          onClick={() => openDetail(rs)}
                          className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded transition"
                        >
                          查看详情
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Detail Modal */}
      {selectedRuleSet !== null && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
              <div>
                <h3 className="text-xl font-bold text-gray-800">{selectedRuleSet.name}</h3>
                <p className="text-sm text-gray-500 mt-0.5">
                  {selectedRuleSet.rule_set_id} · v{selectedRuleSet.version}
                  {selectedRuleSet.description && ` · ${selectedRuleSet.description}`}
                </p>
              </div>
              <button onClick={closeDetail} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">
                ×
              </button>
            </div>

            {/* Modal Body */}
            <div className="overflow-y-auto flex-1 p-6">
              {detailLoading && (
                <div className="text-center py-8 text-gray-500">
                  <div className="animate-spin inline-block w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full mr-2" />
                  加载详情...
                </div>
              )}
              {detailError && (
                <div className="text-center py-8 text-red-500">{detailError}</div>
              )}
              {!detailLoading && !detailError && selectedRuleSet.rules && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-semibold text-gray-700">规则列表</h4>
                    <span className="text-sm text-gray-500">{selectedRuleSet.rules.length} 条规则</span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 text-gray-600 border-b border-gray-200">
                        <tr>
                          <th className="px-4 py-2 text-left font-semibold">规则ID</th>
                          <th className="px-4 py-2 text-left font-semibold">名称</th>
                          <th className="px-4 py-2 text-left font-semibold">类别</th>
                          <th className="px-4 py-2 text-center font-semibold">风险分</th>
                          <th className="px-4 py-2 text-left font-semibold">条件</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {selectedRuleSet.rules.map((rule) => (
                          <tr key={rule.rule_id} className="hover:bg-gray-50">
                            <td className="px-4 py-3 font-mono text-xs text-gray-600">{rule.rule_id}</td>
                            <td className="px-4 py-3 font-medium text-gray-800">{rule.name}</td>
                            <td className="px-4 py-3">
                              <span className="inline-block px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                                {rule.category}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-center">
                              <span className={`inline-block w-10 h-5 leading-5 rounded text-xs font-bold text-white ${rule.risk_score >= 70 ? 'bg-red-500' : rule.risk_score >= 40 ? 'bg-yellow-500' : 'bg-green-500'}`}>
                                {rule.risk_score}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-gray-600 text-xs font-mono max-w-xs truncate" title={rule.condition}>
                              {rule.condition}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end flex-shrink-0">
              <button
                onClick={closeDetail}
                className="px-5 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 transition text-sm"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}