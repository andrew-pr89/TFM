import { useState, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Label,
} from 'recharts'
import { useSummary, useHistory } from '../hooks/useCarbon'
import { format, eachMonthOfInterval, startOfMonth, subMonths } from 'date-fns'

interface Props {
  annualGoalKg?: number
}

const css = (v: string) => getComputedStyle(document.documentElement).getPropertyValue(v).trim()

function catColor(name: string, idx: number): string {
  const map: Record<string, string> = {
    'Alimentación': css('--cat-alimentacion'),
    'Transporte':   css('--cat-transporte'),
    'Energía':      css('--cat-energia'),
    'Residuos':     css('--cat-residuos'),
    'Compras':      css('--cat-compras'),
    'Ocio':         css('--cat-ocio'),
    'Otro':  css('--text-muted'),
  }
  const fallback = [
    css('--c-success'), css('--c-level-adv'), css('--cat-energia'),
    css('--cat-alimentacion'), css('--c-orange'), css('--c-danger'),
  ]
  return map[name] || fallback[idx % fallback.length]
}

const tooltipStyle = {
  background: 'var(--surface-2)',
  border: '1px solid var(--border)',
  borderRadius: '8px',
  fontSize: '12px',
  color: 'var(--text)',
}

function KpiCard({ label, value, unit, sub }: { label: string; value: string | number; unit?: string; sub?: string }) {
  return (
    <div className="kpi-card">
      <span>{label}</span>
      <div>
        <strong>{value}</strong>
        {unit && <span>{unit}</span>}
      </div>
      {sub && <small>{sub}</small>}
    </div>
  )
}

function DonutCenterLabel({ viewBox, total }: { viewBox?: { cx: number; cy: number }; total: number }) {
  const cx = viewBox?.cx ?? 0
  const cy = viewBox?.cy ?? 0
  return (
    <g>
      <text x={cx} y={cy - 7} textAnchor="middle" fill="var(--text-muted)" fontSize={11}>Total</text>
      <text x={cx} y={cy + 11} textAnchor="middle" fill="var(--text)" fontSize={13} fontWeight={700}>
        {total.toFixed(2)} kg
      </text>
    </g>
  )
}

export function SummaryPanel({ annualGoalKg = 6000 }: Props) {
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)

  const activeFrom = dateFrom && dateTo ? dateFrom : undefined
  const activeTo   = dateFrom && dateTo ? dateTo   : undefined

  const { data: summary, isLoading: summaryLoading, isError: summaryError } = useSummary(annualGoalKg, activeFrom, activeTo)
  const { data: rawActivities, isLoading: activitiesLoading } = useHistory(activeFrom, activeTo)

  // ── All hooks must run unconditionally before any early returns ────────────

  const allActivities = rawActivities ?? []

  const uniqueCategories = useMemo(
    () => [...new Set(allActivities.map(a => a.main_category))],
    [allActivities],
  )

  const categoryTotals = useMemo(() => {
    const map: Record<string, number> = {}
    allActivities.forEach(a => {
      const kg = a.emissions.reduce((s, e) => s + e.amount_kg_co2e, 0)
      map[a.main_category] = (map[a.main_category] ?? 0) + kg
    })
    return Object.entries(map)
      .map(([cat, kg]) => ({ name: cat, value: parseFloat(kg.toFixed(3)) }))
      .sort((a, b) => b.value - a.value)
  }, [allActivities])

  const barData = useMemo(() => {
    const now   = new Date()
    const start = activeFrom ? startOfMonth(new Date(activeFrom)) : startOfMonth(subMonths(now, 11))
    const end   = activeTo   ? startOfMonth(new Date(activeTo))   : startOfMonth(now)
    const months = eachMonthOfInterval({ start, end })

    const source = selectedCategory
      ? allActivities.filter(a => a.main_category === selectedCategory)
      : allActivities
    const map = new Map<string, number>()
    source.forEach(a => {
      const key = format(new Date(a.created_at), 'yyyy-MM')
      const kg  = a.emissions.reduce((s, e) => s + e.amount_kg_co2e, 0)
      map.set(key, parseFloat(((map.get(key) ?? 0) + kg).toFixed(3)))
    })

    return months.map(d => ({
      month: format(d, 'MMM yy'),
      kg: map.get(format(d, 'yyyy-MM')) ?? 0,
    }))
  }, [allActivities, selectedCategory, activeFrom, activeTo])

  const pieData = useMemo(() => {
    if (!selectedCategory) return categoryTotals
    const catActs = allActivities.filter(a => a.main_category === selectedCategory)
    const map: Record<string, number> = {}
    catActs.forEach(a =>
      a.emissions.forEach(e => {
        map[e.factor.display_name] = (map[e.factor.display_name] ?? 0) + e.amount_kg_co2e
      }),
    )
    return Object.entries(map)
      .map(([name, value]) => ({ name, value: parseFloat(value.toFixed(3)) }))
      .sort((a, b) => b.value - a.value)
  }, [allActivities, selectedCategory, categoryTotals])

  const stackedData = useMemo(() => {
    const now   = new Date()
    const start = activeFrom ? startOfMonth(new Date(activeFrom)) : startOfMonth(subMonths(now, 11))
    const end   = activeTo   ? startOfMonth(new Date(activeTo))   : startOfMonth(now)
    const months = eachMonthOfInterval({ start, end })

    const map = new Map<string, Record<string, unknown>>()
    months.forEach(d => {
      map.set(format(d, 'yyyy-MM'), { month: format(d, 'MMM yy') })
    })

    allActivities.forEach(a => {
      const key  = format(new Date(a.created_at), 'yyyy-MM')
      const kg   = a.emissions.reduce((s, e) => s + e.amount_kg_co2e, 0)
      const entry = map.get(key)
      if (!entry) return
      entry[a.main_category] = parseFloat((((entry[a.main_category] as number) ?? 0) + kg).toFixed(3))
    })

    return [...map.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([, v]) => v)
  }, [allActivities, activeFrom, activeTo])

  // ── Early returns (after all hooks) ───────────────────────────────────────

  if (summaryLoading || activitiesLoading) return <div className="panel-state">Cargando…</div>
  if (summaryError) return <div className="panel-state panel-state--error">Error al cargar datos.</div>
  if (!summary || summary.total_activities === 0) return (
    <div className="panel-state">
      <p>Sin datos aún.</p>
      <p className="panel-state__hint">Registra actividades para ver tu resumen.</p>
    </div>
  )

  // ── Derived values (non-hook) ──────────────────────────────────────────────

  const pieTotal    = pieData.reduce((s, d) => s + d.value, 0)
  const catActs     = selectedCategory ? allActivities.filter(a => a.main_category === selectedCategory) : []
  const totalCatKg  = catActs.flatMap(a => a.emissions).reduce((s, e) => s + e.amount_kg_co2e, 0)
  const pctBudget   = Math.min((summary.total_kg_co2e / summary.budget_kg_co2e) * 100, 999).toFixed(1)
  const avgAll      = summary.total_activities > 0
    ? (summary.total_kg_co2e / summary.total_activities).toFixed(2)
    : '0'
  const avgCat      = catActs.length > 0 ? (totalCatKg / catActs.length).toFixed(2) : '0'
  const pctOfTotal  = summary.total_kg_co2e > 0
    ? ((totalCatKg / summary.total_kg_co2e) * 100).toFixed(1)
    : '0'
  const barColor    = selectedCategory ? catColor(selectedCategory, 0) : 'var(--accent)'

  return (
    <div className="summary-panel">

      {/* ── Date filter ────────────────────────────────────────────────────── */}
      <div className="date-range-filter">
        <label className="date-range-filter__label">Desde</label>
        <input
          type="date"
          className="date-range-filter__input"
          value={dateFrom}
          max={dateTo || undefined}
          onChange={e => setDateFrom(e.target.value)}
        />
        <label className="date-range-filter__label">Hasta</label>
        <input
          type="date"
          className="date-range-filter__input"
          value={dateTo}
          min={dateFrom || undefined}
          max={new Date().toISOString().split('T')[0]}
          onChange={e => setDateTo(e.target.value)}
        />
        {(dateFrom || dateTo) && (
          <button className="btn-light" onClick={() => { setDateFrom(''); setDateTo('') }}>
            Limpiar
          </button>
        )}
      </div>

      {/* ── Category tabs ──────────────────────────────────────────────────── */}
      <div className="activities-tabs">
        <button
          className={`btn-square${selectedCategory === null ? ' tab-btn--active' : ''}`}
          onClick={() => setSelectedCategory(null)}
        >
          Resumen general
        </button>
        {uniqueCategories.map(cat => (
          <button
            key={cat}
            className={`btn-square${selectedCategory === cat ? ' tab-btn--active' : ''}`}
            onClick={() => setSelectedCategory(cat)}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* ── KPI cards ──────────────────────────────────────────────────────── */}
      <div className="summary-card kpi-grid">
        {selectedCategory ? (
          <>
            <KpiCard label={`CO₂e — ${selectedCategory}`} value={totalCatKg.toFixed(2)} unit="kg" />
            <KpiCard label="Actividades en categoría"      value={catActs.length} />
            <KpiCard label="% del total"                   value={pctOfTotal} unit="%" />
            <KpiCard label="Media por actividad"           value={avgCat} unit="kg" />
          </>
        ) : (
          <>
            <KpiCard label="Total CO₂e"          value={summary.total_kg_co2e.toFixed(2)} unit="kg" />
            <KpiCard label="Total actividades"   value={summary.total_activities} />
            <KpiCard label="Media por actividad" value={avgAll} unit="kg" />
            <KpiCard
              label="Presupuesto mensual"
              value={pctBudget}
              unit="%"
              sub={`${summary.total_kg_co2e.toFixed(0)} / ${summary.budget_kg_co2e.toFixed(0)} kg`}
            />
          </>
        )}
      </div>

      {/* ── Charts row: bar + donut ─────────────────────────────────────────── */}
      <div className="summary-charts-row">

        {/* Bar chart */}
        <div className="chart-wrap">
          <h4>
            {selectedCategory ? `CO₂e mensual — ${selectedCategory}` : 'CO₂e por mes'}
          </h4>
          {barData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={barData} margin={{ top: 4, right: 8, left: -16, bottom: 36 }}>
                <XAxis
                  dataKey="month"
                  tick={{ fontSize: 11, fill: 'var(--text-muted)' }}
                  angle={-35}
                  textAnchor="end"
                  interval={0}
                />
                <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(v: number) => [`${v} kg CO₂e`, '']}
                />
                <Bar dataKey="kg" radius={[4, 4, 0, 0]}>
                  {barData.map((_, i) => (
                    <Cell key={i} fill={barColor} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="chart-empty">Sin datos para el período seleccionado.</p>
          )}
        </div>

        {/* Donut + legend */}
        <div className="chart-wrap">
          <h4>
            {selectedCategory ? `Desglose — ${selectedCategory}` : 'Distribución por categoría'}
          </h4>
          {pieData.length > 0 ? (
            <div className="donut-layout">
              <div className="donut-legend">
                <p>Media actividades</p>
                <p>{avgAll} kg</p>
                {pieData.map((d, i) => (
                  <div key={d.name}>
                    <span style={{ background: catColor(d.name, i) }} />
                    <span title={d.name}>{d.name.length > 35 ? d.name.slice(0, 35) + '…' : d.name}</span>
                    <span>{d.value.toFixed(2)} kg</span>
                    <span>{pieTotal > 0 ? ((d.value / pieTotal) * 100).toFixed(1) : '0'}%</span>
                  </div>
                ))}
                <p>Los valores están expresados en kilogramos (kg).</p>
              </div>
              <div style={{ flexShrink: 0 }}>
                <ResponsiveContainer width={180} height={180}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%" cy="50%"
                      innerRadius={52}
                      outerRadius={80}
                      dataKey="value"
                      strokeWidth={1}
                    >
                      <Label
                        content={<DonutCenterLabel total={pieTotal} />}
                        position="center"
                      />
                      {pieData.map((d, i) => (
                        <Cell key={d.name} fill={catColor(d.name, i)} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={tooltipStyle}
                      formatter={(v: number) => [`${v.toFixed(3)} kg CO₂e`, '']}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          ) : (
            <p className="chart-empty">Sin datos para el período seleccionado.</p>
          )}
        </div>
      </div>

      {/* ── Stacked bar chart ───────────────────────────────────────────────── */}
      {stackedData.length > 0 && (
        <div className="chart-wrap">
          <h4>CO₂e por categoría y mes</h4>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={stackedData} margin={{ top: 4, right: 8, left: -16, bottom: 36 }}>
              <XAxis
                dataKey="month"
                tick={{ fontSize: 11, fill: 'var(--text-muted)' }}
                angle={-35}
                textAnchor="end"
                interval={0}
              />
              <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
              <Tooltip
                contentStyle={tooltipStyle}
                formatter={(v: number, name: string) => [`${v.toFixed(2)} kg`, name]}
              />
              {uniqueCategories.map((cat, i) => (
                <Bar
                  key={cat}
                  dataKey={cat}
                  stackId="a"
                  fill={catColor(cat, i)}
                  radius={i === uniqueCategories.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
          <div className="stacked-legend">
            {uniqueCategories.map((cat, i) => (
              <span key={cat}>
                <span style={{ background: catColor(cat, i) }} />
                {cat}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
