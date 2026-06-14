import { useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie } from 'recharts'
import { useSummary, useHistory } from '../hooks/useCarbon'

interface Props {
  annualGoalKg?: number
}

const COLORS = ['#4ade80', '#86efac', '#a3e635', '#facc15', '#fb923c', '#f97316', '#ef4444']

function co2Color(kg: number) {
  if (kg === 0) return 'var(--c-neutral)'
  if (kg < 1) return 'var(--c-low)'
  if (kg < 5) return 'var(--c-mid)'
  return 'var(--c-high)'
}

const tooltipStyle = {
  background: 'var(--surface-2)',
  border: '1px solid var(--border)',
  borderRadius: '8px',
  fontFamily: 'DM Mono',
  fontSize: '12px',
  color: 'var(--text)',
}

function StatCard({ label, value, unit }: { label: string; value: string | number; unit?: string }) {
  return (
    <div className="stat-card">
      <span className="stat-card__label">{label}</span>
      <span className="stat-card__value">
        {value}
        {unit && <span className="stat-card__unit"> {unit}</span>}
      </span>
    </div>
  )
}

function BudgetCard({ total, budget, periodDays }: { total: number; budget: number; periodDays: number }) {
  const pct = Math.min((total / budget) * 100, 100)
  const over = total > budget
  const barColor = pct < 50 ? '#4ade80' : pct < 80 ? '#facc15' : '#ef4444'

  return (
    <div className="stat-card" style={{ gridColumn: '1 / -1' }}>
      <span className="stat-card__label">Total CO₂e — últimos {periodDays} días</span>
      <div className="budget-card-row">
        <span className="stat-card__value" style={{ color: over ? '#ef4444' : 'inherit' }}>
          {total.toFixed(2)}
        </span>
        <span className="stat-card__unit">
          / {budget.toFixed(0)} kg presupuesto sostenible mensual
        </span>
      </div>
      <div className="budget-bar">
        <div
          className="budget-bar__fill"
          style={{ width: `${pct}%`, background: barColor }}
        />
      </div>
      <span className="budget-pct">
        {pct.toFixed(1)}% del presupuesto{over ? ' — ¡superado!' : ''}
        {' · '}
        Ref: objetivo IPCC 1,5 °C (2 t CO₂/persona/año)
      </span>
    </div>
  )
}

export function SummaryPanel({ annualGoalKg = 6000 }: Props) {
  const { data: summary, isLoading: summaryLoading, isError: summaryError } = useSummary(annualGoalKg)
  const { data: activities, isLoading: activitiesLoading } = useHistory()
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)

  if (summaryLoading || activitiesLoading) return <div className="panel-state">Cargando…</div>
  if (summaryError) return <div className="panel-state panel-state--error">Error al cargar datos.</div>
  if (!summary || summary.total_activities === 0) return (
    <div className="panel-state">
      <span className="panel-state__icon">📊</span>
      <p>Sin datos aún.</p>
      <p className="panel-state__hint">Registra actividades para ver tu resumen.</p>
    </div>
  )

  const uniqueCategories = [...new Set(activities?.map(a => a.main_category) ?? [])]

  // ── Vista de categoría seleccionada ──────────────────────────────────────────
  if (selectedCategory) {
    const catActivities = activities?.filter(a => a.main_category === selectedCategory) ?? []
    const allEmissions = catActivities.flatMap(a => a.emissions)
    const totalCat = allEmissions.reduce((s, e) => s + e.amount_kg_co2e, 0)

    const byFactor = allEmissions.reduce<Record<string, number>>((acc, e) => {
      acc[e.factor.display_name] = (acc[e.factor.display_name] ?? 0) + e.amount_kg_co2e
      return acc
    }, {})
    const chartData = Object.entries(byFactor).map(([name, kg]) => ({
      name,
      value: parseFloat(kg.toFixed(3)),
    }))

    return (
      <div className="summary-panel">
        <button className="tab-btn" onClick={() => setSelectedCategory(null)}>
          ← Volver al resumen
        </button>

        <div className="stat-grid">
          <StatCard label="Total CO₂e" value={totalCat.toFixed(2)} unit="kg" />
          <StatCard label="Actividades" value={catActivities.length} />
        </div>

        {chartData.length > 0 && (
          <div className="chart-wrap">
            <p className="chart-title">Desglose — {selectedCategory}</p>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={chartData}
                  cx="50%" cy="50%"
                  labelLine={true}
                  label={({ name, value }) => `${name}: ${(value as number).toFixed(3)} kg`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: number) => `${value.toFixed(3)} kg CO₂e`}
                  contentStyle={tooltipStyle}
                />
              </PieChart>
            </ResponsiveContainer>

            <div className="emissions-detail">
              {Object.entries(byFactor).map(([name, kg]) => (
                <div key={name} className="emission-row">
                  <span>{name}</span>
                  <span style={{ color: co2Color(kg), fontWeight: 500 }}>
                    {kg.toFixed(3)} kg
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  // ── Vista de resumen general ──────────────────────────────────────────────────
  const perActivity = summary.total_activities > 0
    ? (summary.total_kg_co2e / summary.total_activities).toFixed(2)
    : '0'

  const chartData = summary.top_categories.map((c) => ({
    name: c.category,
    kg: parseFloat(c.total_kg_co2e.toFixed(3)),
  }))

  return (
    <div className="summary-panel">
      <div className="activities-tabs">
        <button
          className={`tab-btn${selectedCategory === null ? ' tab-btn--active' : ''}`}
          onClick={() => setSelectedCategory(null)}
        >
          📊 Resumen General
        </button>
        {uniqueCategories.map(cat => (
          <button
            key={cat}
            className={`tab-btn${selectedCategory === cat ? ' tab-btn--active' : ''}`}
            onClick={() => setSelectedCategory(cat)}
          >
            {cat}
          </button>
        ))}
      </div>

      <div className="stat-grid">
        <BudgetCard total={summary.total_kg_co2e} budget={summary.budget_kg_co2e} periodDays={summary.period_days} />
        <StatCard label="Actividades" value={summary.total_activities} />
        <StatCard label="Media/actividad" value={perActivity} unit="kg" />
      </div>

      {chartData.length > 0 && (
        <div className="chart-wrap">
          <p className="chart-title">Top categorías</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData} margin={{ top: 4, right: 8, left: -16, bottom: 40 }}>
              <XAxis
                dataKey="name"
                tick={{ fontSize: 11, fill: 'var(--text-muted)', fontFamily: 'DM Mono' }}
                angle={-35}
                textAnchor="end"
                interval={0}
              />
              <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)', fontFamily: 'DM Mono' }} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${v} kg CO₂e`, '']} />
              <Bar dataKey="kg" radius={[4, 4, 0, 0]}>
                {chartData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
