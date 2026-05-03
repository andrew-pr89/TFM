import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { useSummary } from '../hooks/useCarbon'

interface Props {
  userId?: string
}

const COLORS = ['#4ade80', '#86efac', '#a3e635', '#facc15', '#fb923c']

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

export function SummaryPanel({ userId = 'default' }: Props) {
  const { data: summary, isLoading, isError } = useSummary(userId)

  if (isLoading) return <div className="panel-state">Calculando resumen…</div>
  if (isError) return <div className="panel-state panel-state--error">Error al cargar el resumen.</div>
  if (!summary || summary.total_activities === 0) return (
    <div className="panel-state">
      <span className="panel-state__icon">📊</span>
      <p>Sin datos aún.</p>
      <p className="panel-state__hint">Registra actividades para ver tu resumen.</p>
    </div>
  )

  const perActivity = summary.total_activities > 0
    ? (summary.total_kg_co2e / summary.total_activities).toFixed(2)
    : '0'

  const chartData = summary.top_categories.map((c) => ({
    name: c.category.replace(/_/g, ' '),
    kg: parseFloat(c.total_kg_co2e.toFixed(3)),
  }))

  return (
    <div className="summary-panel">
      <div className="stat-grid">
        <StatCard label="Total CO₂e" value={summary.total_kg_co2e.toFixed(2)} unit="kg" />
        <StatCard label="Actividades" value={summary.total_activities} />
        <StatCard label="Media/actividad" value={perActivity} unit="kg" />
        <StatCard label="Período" value={summary.period_days} unit="días" />
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
              <Tooltip
                contentStyle={{
                  background: 'var(--surface-2)',
                  border: '1px solid var(--border)',
                  borderRadius: '8px',
                  fontFamily: 'DM Mono',
                  fontSize: '12px',
                  color: 'var(--text)',
                }}
                formatter={(v: number) => [`${v} kg CO₂e`, '']}
              />
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
