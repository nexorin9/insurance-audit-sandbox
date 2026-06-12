import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getSandboxRuns } from '../api/apiClient'
import type { SandboxRun } from '../api/apiClient'
import TrendChart from '../components/TrendChart'
import styles from './Dashboard.module.css'

type SortKey = 'timestamp' | 'high_risk_count'
type SortDir = 'asc' | 'desc'

const PAGE_SIZE = 10

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return ts
  }
}

function getRiskLevel(highRiskCount: number, totalItems: number): 'high' | 'medium' | 'low' {
  if (totalItems === 0) return 'low'
  const ratio = highRiskCount / totalItems
  if (ratio >= 0.3) return 'high'
  if (ratio >= 0.1) return 'medium'
  return 'low'
}

function getRiskLabel(level: 'high' | 'medium' | 'low'): string {
  if (level === 'high') return '高风险'
  if (level === 'medium') return '中风险'
  return '低风险'
}

function getStatusLabel(status: string): { label: string; cls: string } {
  switch (status) {
    case 'completed':
      return { label: '已完成', cls: styles.statusCompleted }
    case 'running':
      return { label: '进行中', cls: styles.statusRunning }
    case 'failed':
      return { label: '失败', cls: styles.statusFailed }
    case 'cancelled':
      return { label: '已取消', cls: styles.statusCancelled }
    default:
      return { label: status, cls: styles.statusCancelled }
  }
}

export default function Dashboard() {
  const navigate = useNavigate()

  // 筛选状态
  const [ruleSetFilter, setRuleSetFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  // 排序状态
  const [sortKey, setSortKey] = useState<SortKey>('timestamp')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  // 分页状态
  const [page, setPage] = useState(1)

  // 获取演练记录
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['sandbox-runs'],
    queryFn: () => getSandboxRuns(1, 1000), // 先拉全部，后端分页
  })

  // 筛选 + 排序
  const filteredRuns = useMemo(() => {
    if (!data?.runs) return []

    let runs: SandboxRun[] = data.runs

    // 规则集名称筛选
    if (ruleSetFilter.trim()) {
      const kw = ruleSetFilter.toLowerCase()
      runs = runs.filter(r => r.rule_set_name?.toLowerCase().includes(kw))
    }

    // 日期范围筛选
    if (dateFrom) {
      runs = runs.filter(r => new Date(r.timestamp) >= new Date(dateFrom))
    }
    if (dateTo) {
      runs = runs.filter(r => new Date(r.timestamp) <= new Date(dateTo + 'T23:59:59'))
    }

    // 排序
    runs = [...runs].sort((a, b) => {
      let cmp = 0
      if (sortKey === 'timestamp') {
        cmp = new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      } else if (sortKey === 'high_risk_count') {
        cmp = a.high_risk_count - b.high_risk_count
      }
      return sortDir === 'asc' ? cmp : -cmp
    })

    return runs
  }, [data, ruleSetFilter, dateFrom, dateTo, sortKey, sortDir])

  // 分页
  const totalItems = filteredRuns.length
  const totalPages = Math.max(1, Math.ceil(totalItems / PAGE_SIZE))
  const currentPage = Math.min(page, totalPages)
  const paginatedRuns = filteredRuns.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
    setPage(1)
  }

  const handleFilter = () => {
    setPage(1)
  }

  const handleReset = () => {
    setRuleSetFilter('')
    setDateFrom('')
    setDateTo('')
    setSortKey('timestamp')
    setSortDir('desc')
    setPage(1)
  }

  const handleRowClick = (runId: string) => {
    navigate(`/sandbox/run/${runId}`)
  }

  const SortIcon = ({ active, dir }: { active: boolean; dir: SortDir }) => (
    <span className={styles.sortIcon}>
      {active ? (dir === 'asc' ? '↑' : '↓') : '↕'}
    </span>
  )

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>演练记录仪表盘</h1>
          <p className={styles.subtitle}>查看历史演练结果，分析高风险费用项趋势</p>
        </div>
      </div>

      {/* 趋势图 */}
      {!isLoading && !isError && data?.runs && (
        <TrendChart runs={data.runs} />
      )}

      {/* 筛选栏 */}
      <div className={styles.filterBar}>
        <input
          type="text"
          className={styles.filterInput}
          placeholder="按规则集名称搜索"
          value={ruleSetFilter}
          onChange={e => setRuleSetFilter(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleFilter()}
        />
        <input
          type="date"
          className={styles.filterInput}
          placeholder="开始日期"
          value={dateFrom}
          onChange={e => setDateFrom(e.target.value)}
        />
        <input
          type="date"
          className={styles.filterInput}
          placeholder="结束日期"
          value={dateTo}
          onChange={e => setDateTo(e.target.value)}
        />
        <button className={styles.filterBtn} onClick={handleFilter}>筛选</button>
        <button className={styles.resetBtn} onClick={handleReset}>重置</button>
      </div>

      {/* 错误提示 */}
      {isError && (
        <div className={styles.errorBox}>
          加载演练记录失败：{error instanceof Error ? error.message : '未知错误'}
        </div>
      )}

      {/* 表格 */}
      <div className={styles.tableCard}>
        {isLoading ? (
          <div className={styles.loadingState}>加载中...</div>
        ) : paginatedRuns.length === 0 ? (
          <div className={styles.emptyState}>
            <div className={styles.emptyIcon}>📋</div>
            <div className={styles.emptyText}>暂无演练记录</div>
            <div className={styles.emptySub}>
              请在「演练执行」页面运行一次演练后返回此处查看结果
            </div>
          </div>
        ) : (
          <>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th onClick={() => handleSort('timestamp')}>
                    执行时间 <SortIcon active={sortKey === 'timestamp'} dir={sortDir} />
                  </th>
                  <th>规则集</th>
                  <th>费用条数</th>
                  <th onClick={() => handleSort('high_risk_count')}>
                    高风险项 <SortIcon active={sortKey === 'high_risk_count'} dir={sortDir} />
                  </th>
                  <th>风险等级</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {paginatedRuns.map(run => {
                  const riskLevel = getRiskLevel(run.high_risk_count, run.total_items)
                  const statusInfo = getStatusLabel(run.status)
                  return (
                    <tr
                      key={run.run_id}
                      className={styles.clickableRow}
                      onClick={() => handleRowClick(run.run_id)}
                    >
                      <td>{formatTimestamp(run.timestamp)}</td>
                      <td>{run.rule_set_name || run.rule_set_id}</td>
                      <td>{run.total_items}</td>
                      <td>
                        <span className={`${styles.riskTag} ${styles[`risk${riskLevel.charAt(0).toUpperCase() + riskLevel.slice(1)}`]}`}>
                          {run.high_risk_count}
                        </span>
                      </td>
                      <td>{getRiskLabel(riskLevel)}</td>
                      <td>
                        <span className={`${styles.statusTag} ${statusInfo.cls}`}>
                          {statusInfo.label}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {/* 分页 */}
            <div className={styles.pagination}>
              <div className={styles.paginationInfo}>
                共 {totalItems} 条记录，第 {currentPage}/{totalPages} 页
              </div>
              <div className={styles.paginationControls}>
                <button
                  className={styles.pageBtn}
                  onClick={() => setPage(1)}
                  disabled={currentPage === 1}
                >
                  首页
                </button>
                <button
                  className={styles.pageBtn}
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                >
                  上一页
                </button>
                <input
                  type="number"
                  className={styles.pageInput}
                  value={currentPage}
                  min={1}
                  max={totalPages}
                  onChange={e => {
                    const v = parseInt(e.target.value)
                    if (!isNaN(v) && v >= 1 && v <= totalPages) setPage(v)
                  }}
                />
                <button
                  className={styles.pageBtn}
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                >
                  下一页
                </button>
                <button
                  className={styles.pageBtn}
                  onClick={() => setPage(totalPages)}
                  disabled={currentPage === totalPages}
                >
                  末页
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}