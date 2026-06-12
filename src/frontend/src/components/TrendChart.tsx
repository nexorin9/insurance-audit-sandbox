import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { SandboxRun } from '../api/apiClient'
import styles from './TrendChart.module.css'

interface TrendChartProps {
  runs: SandboxRun[]
}

type Grouping = 'week' | 'month'

function groupByPeriod(runs: SandboxRun[], grouping: Grouping) {
  if (runs.length === 0) return []

  const sorted = [...runs].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  )

  const groups: Map<string, { timestamp: string; high_risk_count: number; rule_set_name: string; run_id: string }[]> = new Map()

  for (const run of sorted) {
    const d = new Date(run.timestamp)
    let key: string
    let label: string
    if (grouping === 'month') {
      key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
      label = `${d.getFullYear()}/${d.getMonth() + 1}`
    } else {
      // week: ISO week
      const startOfYear = new Date(d.getFullYear(), 0, 1)
      const week = Math.ceil(
        ((d.getTime() - startOfYear.getTime()) / 86400000 + startOfYear.getDay() + 1) / 7
      )
      key = `${d.getFullYear()}-W${String(week).padStart(2, '0')}`
      label = `${d.getFullYear()}W${String(week).padStart(2, '0')}`
    }
    if (!groups.has(key)) {
      groups.set(key, [])
    }
    groups.get(key)!.push({
      timestamp: label,
      high_risk_count: run.high_risk_count,
      rule_set_name: run.rule_set_name || run.rule_set_id,
      run_id: run.run_id,
    })
  }

  return Array.from(groups.entries()).map(([key, items]) => ({
    key,
    label: items[0].timestamp,
    high_risk_count: Math.max(...items.map(i => i.high_risk_count)),
    rule_set_name: items[items.length - 1].rule_set_name,
    run_id: items[items.length - 1].run_id,
    is_rule_change: false,
  }))
}

function detectRuleChanges(grouped: ReturnType<typeof groupByPeriod>) {
  if (grouped.length < 2) return grouped
  const result = [...grouped]
  for (let i = 1; i < result.length; i++) {
    if (result[i].rule_set_name !== result[i - 1].rule_set_name) {
      result[i].is_rule_change = true
    }
  }
  return result
}

const CHART_W = 800
const CHART_H = 200
const PAD_L = 50
const PAD_R = 20
const PAD_T = 20
const PAD_B = 40
const INNER_W = CHART_W - PAD_L - PAD_R
const INNER_H = CHART_H - PAD_T - PAD_B

export default function TrendChart({ runs }: TrendChartProps) {
  const navigate = useNavigate()
  const [grouping, setGrouping] = useState<'week' | 'month'>('week')

  const grouped = groupByPeriod(runs, grouping)
  const withRuleChange = detectRuleChanges(grouped)

  if (withRuleChange.length === 0) {
    return (
      <div className={styles.container}>
        <div className={styles.header}>
          <span className={styles.title}>演练历史趋势</span>
          <span className={styles.emptyHint}>暂无数据，无法绘制趋势图</span>
        </div>
      </div>
    )
  }

  const maxY = Math.max(...withRuleChange.map(d => d.high_risk_count), 1)
  const xStep = withRuleChange.length > 1 ? INNER_W / (withRuleChange.length - 1) : 0

  const points = withRuleChange.map((d, i) => ({
    ...d,
    cx: PAD_L + i * xStep,
    cy: PAD_T + INNER_H - (d.high_risk_count / maxY) * INNER_H,
  }))

  // Y-axis ticks (5 ticks)
  const yTicks = Array.from({ length: 5 }, (_, i) => {
    const value = Math.round((maxY / 4) * i)
    const y = PAD_T + INNER_H - (value / maxY) * INNER_H
    return { value, y }
  })

  // X-axis labels (show all if <= 10, otherwise sample)
  const xLabels = withRuleChange.length <= 10
    ? withRuleChange.map((d, i) => ({ label: d.label, cx: PAD_L + i * xStep }))
    : withRuleChange
        .filter((_, i) => i % Math.ceil(withRuleChange.length / 8) === 0)
        .map((d) => {
          const idx = withRuleChange.findIndex(x => x.key === d.key)
          return { label: d.label, cx: PAD_L + idx * xStep }
        })

  // Polyline path
  const polyline = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.cx.toFixed(1)} ${p.cy.toFixed(1)}`)
    .join(' ')

  const handlePointClick = (runId: string) => {
    navigate(`/sandbox/run/${runId}`)
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.title}>演练历史趋势</span>
        <div className={styles.controls}>
          <button
            className={`${styles.groupBtn} ${grouping === 'week' ? styles.groupBtnActive : ''}`}
            onClick={() => setGrouping('week')}
          >
            按周
          </button>
          <button
            className={`${styles.groupBtn} ${grouping === 'month' ? styles.groupBtnActive : ''}`}
            onClick={() => setGrouping('month')}
          >
            按月
          </button>
        </div>
      </div>
      <div className={styles.chartWrapper}>
        <svg
          viewBox={`0 0 ${CHART_W} ${CHART_H}`}
          className={styles.svg}
          aria-label="演练历史趋势图"
        >
          {/* Grid lines */}
          {yTicks.map((tick, i) => (
            <g key={i}>
              <line
                x1={PAD_L}
                y1={tick.y}
                x2={CHART_W - PAD_R}
                y2={tick.y}
                stroke="#e5e7eb"
                strokeWidth="1"
                strokeDasharray={i === 0 ? 'none' : '4,4'}
              />
              <text
                x={PAD_L - 8}
                y={tick.y + 4}
                textAnchor="end"
                className={styles.axisLabel}
              >
                {tick.value}
              </text>
            </g>
          ))}

          {/* X-axis */}
          <line
            x1={PAD_L}
            y1={PAD_T + INNER_H}
            x2={CHART_W - PAD_R}
            y2={PAD_T + INNER_H}
            stroke="#d1d5db"
            strokeWidth="1"
          />

          {/* X-axis labels */}
          {xLabels.map((l, i) => (
            <text
              key={i}
              x={l.cx}
              y={PAD_T + INNER_H + 20}
              textAnchor="middle"
              className={styles.axisLabel}
            >
              {l.label}
            </text>
          ))}

          {/* Y-axis label */}
          <text
            x={12}
            y={PAD_T + INNER_H / 2}
            textAnchor="middle"
            className={styles.axisLabel}
            transform={`rotate(-90, 12, ${PAD_T + INNER_H / 2})`}
          >
            高风险项数
          </text>

          {/* Rule change vertical markers */}
          {points
            .filter(p => p.is_rule_change)
            .map((p, i) => (
              <g key={`rule-${i}`}>
                <line
                  x1={p.cx}
                  y1={PAD_T}
                  x2={p.cx}
                  y2={PAD_T + INNER_H}
                  stroke="#f59e0b"
                  strokeWidth="2"
                  strokeDasharray="6,3"
                />
                <circle cx={p.cx} cy={p.cy} r="6" fill="#f59e0b" />
                <text
                  x={p.cx + 8}
                  y={PAD_T + 14}
                  className={styles.ruleChangeLabel}
                >
                  规则变更
                </text>
              </g>
            ))}

          {/* Area fill */}
          <defs>
            <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.15" />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
            </linearGradient>
          </defs>
          {points.length > 1 && (
            <path
              d={`${polyline} L ${points[points.length - 1].cx.toFixed(1)} ${(PAD_T + INNER_H).toFixed(1)} L ${points[0].cx.toFixed(1)} ${(PAD_T + INNER_H).toFixed(1)} Z`}
              fill="url(#areaGradient)"
            />
          )}

          {/* Trend line */}
          {points.length > 1 && (
            <polyline
              points={polyline}
              fill="none"
              stroke="#3b82f6"
              strokeWidth="2.5"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          )}

          {/* Data points */}
          {points.map((p, i) => (
            <g
              key={i}
              onClick={() => handlePointClick(p.run_id)}
              style={{ cursor: 'pointer' }}
              aria-label={`${p.label} 高风险项: ${p.high_risk_count}`}
            >
              <circle
                cx={p.cx}
                cy={p.cy}
                r={p.is_rule_change ? 8 : 5}
                fill={p.is_rule_change ? '#f59e0b' : '#3b82f6'}
                stroke="white"
                strokeWidth="2"
              />
              {/* Tooltip on hover via title */}
              <title>{p.label} | 高风险项: {p.high_risk_count} | 规则集: {p.rule_set_name}</title>
            </g>
          ))}
        </svg>
      </div>
      <div className={styles.legend}>
        <span className={styles.legendDot} style={{ background: '#3b82f6' }} />
        <span>高风险项趋势</span>
        <span className={styles.legendDot} style={{ background: '#f59e0b' }} />
        <span>规则变更点</span>
        <span className={styles.legendHint}>（点击数据点可跳转到对应演练详情）</span>
      </div>
    </div>
  )
}