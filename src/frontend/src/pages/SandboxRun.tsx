import { useState, useRef, useCallback, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getRules, runSandbox, getSandboxRun, generateReport } from '../api/apiClient'
import type { FeeItem } from '../api/apiClient'
import styles from './SandboxRun.module.css'

interface TopRiskCategory {
  category: string
  avg_score: number
  hit_count: number
}

interface RiskDistribution {
  [category: string]: {
    hit_count: number
    avg_score: number
  }
}

interface SandboxRunResult {
  run_id: string
  timestamp: string
  rule_set_id: string
  rule_set_name: string
  total_items: number
  hit_count: number
  high_risk_count: number
  risk_distribution: RiskDistribution
  top_risk_categories: TopRiskCategory[]
  hit_items: Array<FeeItem & { rule_id: string; risk_score: number }>
}

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return ts
  }
}

function getRiskColor(score: number): 'high' | 'medium' | 'low' {
  if (score >= 70) return 'high'
  if (score >= 40) return 'medium'
  return 'low'
}

export default function SandboxRun() {
  // 规则集选择
  const [selectedRuleSetId, setSelectedRuleSetId] = useState('')
  const [ruleSetError, setRuleSetError] = useState('')

  // 文件上传
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [feeItems, setFeeItems] = useState<FeeItem[]>([])
  const [uploadError, setUploadError] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 执行状态
  const [running, setRunning] = useState(false)
  const [executeError, setExecuteError] = useState('')
  const [progress, setProgress] = useState(0)

  // 结果
  const [runResult, setRunResult] = useState<SandboxRunResult | null>(null)
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null)
  const [downloading, setDownloading] = useState<'pdf' | 'docx' | null>(null)

  // 获取规则集列表
  const { data: ruleSets } = useQuery({
    queryKey: ['rule-sets'],
    queryFn: getRules,
  })

  // 选中的规则集详情
  const selectedRuleSet = useMemo(() => {
    return ruleSets?.find(rs => rs.rule_set_id === selectedRuleSetId)
  }, [ruleSets, selectedRuleSetId])

  // 处理文件选择
  const handleFileSelect = useCallback((file: File) => {
    setUploadError('')
    setExecuteError('')

    if (!file.name.endsWith('.json')) {
      setUploadError('请上传 JSON 格式的费用数据文件')
      return
    }

    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const text = e.target?.result as string
        const parsed = JSON.parse(text)

        let items: FeeItem[] = []
        if (Array.isArray(parsed)) {
          items = parsed
        } else if (parsed.fee_items && Array.isArray(parsed.fee_items)) {
          items = parsed.fee_items
        } else if (parsed.items && Array.isArray(parsed.items)) {
          items = parsed.items
        }

        if (!Array.isArray(items) || items.length === 0) {
          setUploadError('JSON 文件内容格式不正确，请确认包含费用明细数组')
          return
        }

        // 简单字段校验
        const invalid = items.find(item => !item.item_id || item.amount === undefined)
        if (invalid) {
          setUploadError('费用数据缺少必需字段（item_id、amount），请检查数据格式')
          return
        }

        setSelectedFile(file)
        setFeeItems(items)
      } catch {
        setUploadError('JSON 文件解析失败，请检查文件内容是否为合法 JSON')
      }
    }
    reader.readAsText(file)
  }, [])

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFileSelect(file)
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFileSelect(file)
  }, [handleFileSelect])

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
  }

  const handleDragLeave = () => setDragOver(false)

  const handleRemoveFile = () => {
    setSelectedFile(null)
    setFeeItems([])
    setUploadError('')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  // 执行演练
  const handleExecute = async () => {
    setExecuteError('')
    setRuleSetError('')

    if (!selectedRuleSetId) {
      setRuleSetError('请先选择一个规则集')
      return
    }
    if (feeItems.length === 0) {
      setExecuteError('请先上传费用数据文件')
      return
    }

    setRunning(true)
    setProgress(10)

    try {
      setProgress(30)
      const result = await runSandbox(selectedRuleSetId, feeItems)
      setProgress(70)

      // 轮询获取完整结果
      let runResult: SandboxRunResult | null = null
      let attempts = 0
      while (attempts < 20) {
        await new Promise(r => setTimeout(r, 500))
        const detail = await getSandboxRun(result.run_id)
        if (detail.status === 'completed') {
          runResult = detail as SandboxRunResult
          break
        }
        if (detail.status === 'failed') {
          throw new Error('演练执行失败')
        }
        attempts++
      }

      setProgress(90)
      if (!runResult) {
        // 直接使用返回的初步结果
        runResult = result as SandboxRunResult
      }

      setRunResult(runResult)
      setProgress(100)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '未知错误'
      setExecuteError(`演练执行失败：${msg}`)
      setRunResult(null)
    } finally {
      setRunning(false)
      setTimeout(() => setProgress(0), 800)
    }
  }

  // 下载报告
  const handleDownloadReport = async (format: 'pdf' | 'docx') => {
    if (!runResult) return
    setDownloading(format)
    try {
      const blob = await generateReport(runResult.run_id, format)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `整改建议报告_${runResult.run_id.slice(0, 8)}.${format}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch {
      alert(`${format.toUpperCase()} 报告下载失败，请检查服务是否启动`)
    } finally {
      setDownloading(null)
    }
  }

  // 风险分布数据
  const riskDistributionData = useMemo(() => {
    if (!runResult?.risk_distribution) return []
    return Object.entries(runResult.risk_distribution).map(([category, data]) => ({
      category,
      hit_count: data.hit_count,
      avg_score: data.avg_score,
    }))
  }, [runResult?.risk_distribution])

  const maxHitCount = useMemo(() => {
    return Math.max(...riskDistributionData.map(d => d.hit_count), 1)
  }, [riskDistributionData])

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title}>演练执行</h1>
        <p className={styles.subtitle}>选择规则集 → 上传脱敏费用数据 → 执行演练 → 下载整改建议报告</p>
      </div>

      {/* 执行区域 */}
      <div className={styles.twoCol}>
        {/* 规则集选择 */}
        <div className={styles.ruleSetSection}>
          <h2 className={styles.cardTitle}>步骤 1：选择规则集</h2>
          <div className={styles.selectRow}>
            <select
              className={`${styles.ruleSelect} ${ruleSetError ? styles.error : ''}`}
              value={selectedRuleSetId}
              onChange={e => {
                setSelectedRuleSetId(e.target.value)
                setRuleSetError('')
              }}
            >
              <option value="">— 请选择规则集 —</option>
              {ruleSets?.map(rs => (
                <option key={rs.rule_set_id} value={rs.rule_set_id}>
                  {rs.name}（v{rs.version}，{rs.rule_count} 条规则）
                </option>
              ))}
            </select>
          </div>
          {ruleSetError && <div className={styles.errorBox}>{ruleSetError}</div>}

          {selectedRuleSet && (
            <div className={styles.ruleDetail}>
              <div className={styles.ruleDetailTitle}>规则集详情</div>
              <div className={styles.ruleDetailRow}>
                <span className={styles.ruleDetailLabel}>ID：</span>
                <span>{selectedRuleSet.rule_set_id}</span>
              </div>
              <div className={styles.ruleDetailRow}>
                <span className={styles.ruleDetailLabel}>版本：</span>
                <span>{selectedRuleSet.version}</span>
              </div>
              <div className={styles.ruleDetailRow}>
                <span className={styles.ruleDetailLabel}>规则数：</span>
                <span>{selectedRuleSet.rule_count} 条</span>
              </div>
            </div>
          )}
        </div>

        {/* 文件上传 */}
        <div className={styles.uploadSection}>
          <h2 className={styles.cardTitle}>步骤 2：上传费用数据</h2>

          <div
            className={`${styles.dropZone} ${dragOver ? styles.dragOver : ''} ${uploadError ? styles.error : ''}`}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => fileInputRef.current?.click()}
          >
            <div className={styles.dropIcon}>📂</div>
            <div className={styles.dropText}>
              拖拽 JSON 文件到此处，或点击选择文件
            </div>
            <div className={styles.dropHint}>
              支持 fee_sample_50.json、fee_sample_100.json 等格式
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".json"
              className={styles.fileInput}
              onChange={handleFileInputChange}
            />
          </div>

          {uploadError && <div className={styles.errorBox}>{uploadError}</div>}

          {selectedFile && (
            <div className={styles.fileInfo}>
              <div className={styles.fileIcon}>📄</div>
              <div className={styles.fileDetails}>
                <div className={styles.fileName}>{selectedFile.name}</div>
                <div className={styles.fileMeta}>
                  共 {feeItems.length} 条费用明细
                </div>
              </div>
              <button className={styles.removeFile} onClick={handleRemoveFile}>
                移除
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 执行按钮 */}
      <div className={styles.card}>
        <button
          className={`${styles.executeBtn} ${running ? styles.running : ''}`}
          onClick={handleExecute}
          disabled={running}
        >
          {running ? (
            <>
              <div className={styles.spinner} />
              演练执行中…
            </>
          ) : (
            '▶ 执行演练'
          )}
        </button>

        {running && progress > 0 && (
          <div className={styles.progressBar}>
            <div className={styles.progressFill} style={{ width: `${progress}%` }} />
          </div>
        )}

        {executeError && <div className={styles.errorBox}>{executeError}</div>}
      </div>

      {/* 演练结果 */}
      {runResult && (
        <div className={styles.resultCard}>
          <div className={styles.resultHeader}>
            <h2 className={styles.resultTitle}>演练结果</h2>
            <span className={styles.runId}>run_id: {runResult.run_id}</span>
          </div>

          {/* 统计指标 */}
          <div className={styles.statsRow}>
            <div className={styles.statBox}>
              <div className={styles.statValue}>{runResult.total_items}</div>
              <div className={styles.statLabel}>费用总条数</div>
            </div>
            <div className={styles.statBox}>
              <div className={`${styles.statValue} ${runResult.hit_count > 0 ? styles.danger : styles.success}`}>
                {runResult.hit_count}
              </div>
              <div className={styles.statLabel}>命中规则条数</div>
            </div>
            <div className={styles.statBox}>
              <div className={`${styles.statValue} ${runResult.high_risk_count > 0 ? styles.danger : styles.success}`}>
                {runResult.high_risk_count}
              </div>
              <div className={styles.statLabel}>高风险项数量</div>
            </div>
            <div className={styles.statBox}>
              <div className={styles.statValue}>{formatTimestamp(runResult.timestamp)}</div>
              <div className={styles.statLabel}>执行时间</div>
            </div>
          </div>

          {/* 风险分布 */}
          {riskDistributionData.length > 0 && (
            <div className={styles.riskDistSection}>
              <div className={styles.sectionTitle}>风险分布（按类别）</div>
              <div className={styles.riskBars}>
                {riskDistributionData.map(({ category, hit_count, avg_score }) => {
                  const pct = (hit_count / maxHitCount) * 100
                  const color = getRiskColor(avg_score)
                  return (
                    <div key={category} className={styles.riskBarItem}>
                      <div className={styles.riskBarLabel}>{category}</div>
                      <div className={styles.riskBarTrack}>
                        <div
                          className={`${styles.riskBarFill} ${styles[color]}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <div className={styles.riskBarValue}>
                        {hit_count} 条 | {avg_score.toFixed(1)}分
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* TOP 高风险类别下钻 */}
          {runResult.top_risk_categories && runResult.top_risk_categories.length > 0 && (
            <div className={styles.topRiskSection}>
              <div className={styles.sectionTitle}>TOP 高风险类别</div>
              {runResult.top_risk_categories.map(cat => {
                const isOpen = expandedCategory === cat.category
                const drillItems = runResult.hit_items?.filter(
                  item => item.category === cat.category
                ) || []

                return (
                  <div key={cat.category} style={{ marginBottom: 8 }}>
                    <button
                      className={`${styles.expandBtn} ${isOpen ? styles.active : ''}`}
                      onClick={() => setExpandedCategory(isOpen ? null : cat.category)}
                    >
                      <span>
                        {cat.category}（{cat.hit_count} 条，平均风险 {cat.avg_score.toFixed(1)} 分）
                      </span>
                      <span className={`${styles.expandIcon} ${isOpen ? styles.open : ''}`}>
                        ▼
                      </span>
                    </button>

                    {isOpen && (
                      <div className={styles.drillDownPanel}>
                        {drillItems.length === 0 ? (
                          <div className={styles.emptyState}>无明细数据</div>
                        ) : (
                          <table className={styles.drillDownTable}>
                            <thead>
                              <tr>
                                <th>费用ID</th>
                                <th>类别</th>
                                <th>金额</th>
                                <th>风险分</th>
                                <th>命中规则</th>
                              </tr>
                            </thead>
                            <tbody>
                              {drillItems.slice(0, 50).map((item, idx) => (
                                <tr key={idx}>
                                  <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{item.item_id.slice(0, 12)}…</td>
                                  <td>{item.category}</td>
                                  <td>¥{item.amount.toFixed(2)}</td>
                                  <td>
                                    <span style={{
                                      color: item.risk_score >= 70 ? '#dc2626' : item.risk_score >= 40 ? '#d97706' : '#059669',
                                      fontWeight: 600,
                                    }}>
                                      {item.risk_score.toFixed(1)}
                                    </span>
                                  </td>
                                  <td style={{ fontSize: 12, color: '#6b7280' }}>{item.rule_id}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* 报告下载 */}
          <div className={styles.reportActions}>
            <button
              className={`${styles.reportBtn} ${styles.pdf}`}
              onClick={() => handleDownloadReport('pdf')}
              disabled={downloading !== null}
            >
              {downloading === 'pdf' ? '下载中…' : '📥 下载 PDF 报告'}
            </button>
            <button
              className={`${styles.reportBtn} ${styles.docx}`}
              onClick={() => handleDownloadReport('docx')}
              disabled={downloading !== null}
            >
              {downloading === 'docx' ? '下载中…' : '📥 下载 Word 报告'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}