import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getSandboxRun, generateReport } from '../api/apiClient'
import type { SandboxRun } from '../api/apiClient'
import styles from './ReportView.module.css'

interface HitItem {
  item_id: string
  category: string
  amount: number
  unit_price?: number
  risk_score: number
  matched_rules: string[]
}

interface RiskDistribution {
  [category: string]: {
    hit_count: number
    avg_score: number
  }
}

interface RunDetail extends SandboxRun {
  hit_items: HitItem[]
  risk_distribution: RiskDistribution
  top_risk_categories: Array<{
    category: string
    avg_score: number
    hit_count: number
  }>
}

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
  } catch {
    return ts
  }
}

function getRiskLabel(score: number): { label: string; cls: string } {
  if (score >= 70) return { label: '高风险', cls: styles.riskHigh }
  if (score >= 40) return { label: '中风险', cls: styles.riskMedium }
  return { label: '低风险', cls: styles.riskLow }
}

function getRiskBarClass(score: number): string {
  if (score >= 70) return styles.high
  if (score >= 40) return styles.medium
  return styles.low
}

export default function ReportView() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [downloading, setDownloading] = useState<'pdf' | 'docx' | null>(null)

  const { data: runDetail, isLoading, isError, error } = useQuery({
    queryKey: ['sandbox-run', runId],
    queryFn: () => getSandboxRun(runId!),
    enabled: !!runId,
  })

  const handleDownload = async (format: 'pdf' | 'docx') => {
    if (!runId) return
    setDownloading(format)
    try {
      const blob = await generateReport(runId, format)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `演练报告_${runId}.${format}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('下载失败:', e)
    } finally {
      setDownloading(null)
    }
  }

  const handlePreview = async (format: 'pdf' | 'docx') => {
    if (!runId) return
    try {
      const blob = await generateReport(runId, format)
      const url = URL.createObjectURL(blob)
      setPreviewUrl(url)
      setPreviewOpen(true)
    } catch (e) {
      console.error('预览加载失败:', e)
    }
  }

  const closePreview = () => {
    setPreviewOpen(false)
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl)
      setPreviewUrl(null)
    }
  }

  if (!runId) {
    return (
      <div className={styles.container}>
        <div className={styles.errorBox}>缺少演练记录 ID</div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className={styles.container}>
        <div className={styles.loadingState}>加载中...</div>
      </div>
    )
  }

  if (isError || !runDetail) {
    return (
      <div className={styles.container}>
        <button className={styles.backBtn} onClick={() => navigate('/dashboard')}>
          ← 返回仪表盘
        </button>
        <div className={styles.errorBox}>
          加载演练记录失败：{error instanceof Error ? error.message : '未知错误'}
        </div>
      </div>
    )
  }

  const detail = runDetail as unknown as RunDetail
  const hitItems = detail.hit_items || []
  const riskDist = detail.risk_distribution || {}
  const topRisk = detail.top_risk_categories || []

  // Build risk distribution chart data
  const chartData = Object.entries(riskDist).map(([category, data]) => ({
    category,
    hitCount: data.hit_count,
    avgScore: data.avg_score,
  })).sort((a, b) => b.hitCount - a.hitCount)

  const maxHit = chartData.length > 0 ? Math.max(...chartData.map(d => d.hitCount)) : 1

  // Calculate high_risk_count from risk distribution
  const highRiskCount = Object.entries(riskDist).reduce((sum, [, data]) => {
    if (data.avg_score >= 70) return sum + data.hit_count
    return sum
  }, 0)

  return (
    <div className={styles.container}>
      <button className={styles.backBtn} onClick={() => navigate('/dashboard')}>
        ← 返回仪表盘
      </button>

      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>演练报告详情</h1>
          <p className={styles.subtitle}>演练 ID：{runId}</p>
        </div>
        <div className={styles.downloadBtns}>
          <button
            className={`${styles.downloadBtn} ${styles.pdfBtn}`}
            onClick={() => handleDownload('pdf')}
            disabled={downloading !== null}
          >
            {downloading === 'pdf' ? '生成中...' : '📄 下载 PDF'}
          </button>
          <button
            className={`${styles.downloadBtn} ${styles.docxBtn}`}
            onClick={() => handleDownload('docx')}
            disabled={downloading !== null}
          >
            {downloading === 'docx' ? '生成中...' : '📝 下载 Word'}
          </button>
          <button
            className={`${styles.downloadBtn}`}
            style={{ background: '#6b7280', color: '#fff' }}
            onClick={() => handlePreview('pdf')}
          >
            👁 预览 PDF
          </button>
        </div>
      </div>

      {/* 摘要卡片 */}
      <div className={styles.summaryCard}>
        <h2 className={styles.summaryTitle}>演练摘要</h2>
        <div className={styles.summaryGrid}>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>演练 ID</span>
            <span className={styles.summaryValue} style={{ fontSize: '14px' }}>{runId}</span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>规则集</span>
            <span className={styles.summaryValue}>{detail.rule_set_name || detail.rule_set_id}</span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>执行时间</span>
            <span className={styles.summaryValue} style={{ fontSize: '14px' }}>
              {formatTimestamp(detail.timestamp)}
            </span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>费用条数</span>
            <span className={styles.summaryValue}>{detail.total_items ?? 0}</span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>命中条数</span>
            <span className={styles.summaryValue}>{hitItems.length > 0 ? hitItems.length : (detail.hit_count ?? 0)}</span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>高风险项</span>
            <span className={`${styles.summaryValue} ${styles.high}`}>
              {highRiskCount > 0 ? highRiskCount : (detail.high_risk_count ?? 0)}
            </span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>状态</span>
            <span className={styles.summaryValue}>
              {detail.status === 'completed' ? '已完成' : detail.status}
            </span>
          </div>
        </div>
      </div>

      {/* 风险分布图 */}
      {chartData.length > 0 && (
        <div className={styles.chartCard}>
          <h2 className={styles.chartTitle}>风险分布（按类别）</h2>
          <div className={styles.chartContainer}>
            <div className={styles.barChart}>
              {chartData.slice(0, 8).map(item => {
                const barHeight = maxHit > 0 ? Math.max((item.hitCount / maxHit) * 160, 8) : 8
                return (
                  <div key={item.category} className={styles.barGroup}>
                    <div className={styles.barValue}>{item.hitCount}</div>
                    <div
                      className={`${styles.bar} ${getRiskBarClass(item.avgScore)}`}
                      style={{ height: `${barHeight}px` }}
                      title={`${item.category}: ${item.hitCount}条, 平均风险 ${item.avgScore.toFixed(1)}`}
                    />
                    <div className={styles.xLabel}>{item.category}</div>
                  </div>
                )
              })}
            </div>
          </div>
          <div className={styles.legend}>
            <div className={styles.legendItem}>
              <div className={styles.legendDot} style={{ background: '#dc2626' }} />
              高风险（≥70分）
            </div>
            <div className={styles.legendItem}>
              <div className={styles.legendDot} style={{ background: '#f59e0b' }} />
              中风险（40-69分）
            </div>
            <div className={styles.legendItem}>
              <div className={styles.legendDot} style={{ background: '#10b981' }} />
              低风险（{'<'}40分）
            </div>
          </div>
        </div>
      )}

      {/* TOP 高风险类别 */}
      {topRisk.length > 0 && (
        <div className={styles.summaryCard}>
          <h2 className={styles.summaryTitle}>TOP 高风险类别</h2>
          <div className={styles.summaryGrid}>
            {topRisk.slice(0, 6).map((item, idx) => {
              const riskInfo = getRiskLabel(item.avg_score)
              return (
                <div key={idx} className={styles.summaryItem}>
                  <span className={styles.summaryLabel}>#{idx + 1} {item.category}</span>
                  <span className={`${styles.summaryValue} ${riskInfo.cls.replace(styles.riskHigh, styles.high).replace(styles.riskMedium, styles.medium).replace(styles.riskLow, styles.low)}`}>
                    {item.avg_score.toFixed(1)} 分 · {item.hit_count} 条
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 高风险项明细 */}
      {hitItems.length > 0 && (
        <div className={styles.hitItemsCard}>
          <h2 className={styles.hitItemsTitle}>
            高风险项明细（共 {hitItems.length} 条）
          </h2>
          <div className={styles.hitItemRow + ' ' + styles.header}>
            <div>费用ID</div>
            <div>类别</div>
            <div>金额（元）</div>
            <div>风险评分</div>
            <div>命中规则</div>
          </div>
          {hitItems.slice(0, 50).map((item, idx) => {
            const riskInfo = getRiskLabel(item.risk_score)
            return (
              <div key={idx} className={styles.hitItemRow}>
                <div style={{ fontFamily: 'monospace', fontSize: '12px' }}>{item.item_id.slice(0, 12)}...</div>
                <div>{item.category}</div>
                <div>¥{item.amount.toFixed(2)}</div>
                <div>
                  <span className={`${styles.riskTag} ${riskInfo.cls}`}>
                    {item.risk_score.toFixed(0)}
                  </span>
                </div>
                <div style={{ fontSize: '12px', color: '#6b7280' }}>
                  {item.matched_rules?.join(', ') || '-'}
                </div>
              </div>
            )
          })}
          {hitItems.length > 50 && (
            <div style={{ textAlign: 'center', padding: '12px', color: '#6b7280', fontSize: '13px' }}>
              仅显示前 50 条，共 {hitItems.length} 条高风险项
            </div>
          )}
        </div>
      )}

      {/* 预览弹窗 */}
      {previewOpen && previewUrl && (
        <div className={styles.previewModal} onClick={closePreview}>
          <div className={styles.previewContent} onClick={e => e.stopPropagation()}>
            <div className={styles.previewHeader}>
              <h3 className={styles.previewTitle}>报告预览</h3>
              <button className={styles.closeBtn} onClick={closePreview}>关闭</button>
            </div>
            <iframe
              src={previewUrl}
              className={styles.previewFrame}
              title="报告预览"
            />
          </div>
        </div>
      )}
    </div>
  )
}