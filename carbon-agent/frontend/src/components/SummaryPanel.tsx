import { useState } from 'react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie } from 'recharts'
import { useSummary, useHistory } from '../hooks/useCarbon'
import type { ActivityOut } from '../types'

interface Props {
  userId?: string
}

const COLORS = ['#4ade80', '#86efac', '#a3e635', '#facc15', '#fb923c', '#f97316', '#ef4444']

function co2Color(kg: number) {
  if (kg === 0) return 'var(--c-neutral)'
  if (kg < 1) return 'var(--c-low)'
  if (kg < 5) return 'var(--c-mid)'
  return 'var(--c-high)'
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

export function SummaryPanel({ userId = 'default' }: Props) {
  const { data: summary, isLoading: summaryLoading, isError: summaryError } = useSummary(userId)
  const { data: activities, isLoading: activitiesLoading } = useHistory(userId)
  const [selectedActivityId, setSelectedActivityId] = useState<number | null>(null)

  if (summaryLoading || activitiesLoading) return <div className="panel-state">Cargando…</div>
  if (summaryError) return <div className="panel-state panel-state--error">Error al cargar datos.</div>
  if (!summary || summary.total_activities === 0) return (
    <div className="panel-state">
      <span className="panel-state__icon">📊</span>
      <p>Sin datos aún.</p>
      <p className="panel-state__hint">Registra actividades para ver tu resumen.</p>
    </div>
  )

  const selectedActivity = activities?.find(a => a.id === selectedActivityId)

  // Si hay actividad seleccionada, mostrar dashboard de esa actividad
  if (selectedActivity) {
    const total = selectedActivity.emissions.reduce((s, e) => s + e.amount_kg_co2e, 0)
    const chartData = selectedActivity.emissions.map(e => ({
      name: e.factor.display_name,
      value: parseFloat(e.amount_kg_co2e.toFixed(3)),
      kg: e.amount_kg_co2e,
    }))

    return (
      <div className="summary-panel">
        <div className="dashboard-header">
          <button
            className="btn-back"
            onClick={() => setSelectedActivityId(null)}
            style={{ marginBottom: '16px', padding: '8px 12px', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: '6px', cursor: 'pointer' }}
          >
            ← Volver al resumen
          </button>
        </div>

        <div className="activity-detail">
          <p className="activity-detail__text" style={{ marginBottom: '16px', padding: '12px', background: 'var(--surface-2)', borderRadius: '8px' }}>
            {selectedActivity.raw_text}
          </p>
          <p className="activity-detail__date" style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '16px' }}>
            {format(new Date(selectedActivity.created_at), 'd MMM, HH:mm', { locale: es })}
          </p>
        </div>

        <div className="stat-grid" style={{ marginBottom: '24px' }}>
          <StatCard label="Total CO₂e" value={total.toFixed(2)} unit="kg" />
          <StatCard label="Factores" value={selectedActivity.emissions.length} />
        </div>

        {chartData.length > 0 && (
          <div className="chart-wrap" style={{ marginBottom: '24px' }}>
            <p className="chart-title">Desglose de emisiones</p>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  labelLine={true}
                  label={({ name, value }) => `${name}: ${value.toFixed(3)} kg`}
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
                  contentStyle={{
                    background: 'var(--surface-2)',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    fontFamily: 'DM Mono',
                    fontSize: '12px',
                    color: 'var(--text)',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>

            <div className="emissions-detail" style={{ marginTop: '16px' }}>
              {selectedActivity.emissions.map((e) => (
                <div key={e.id} className="emission-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                  <span>{e.factor.display_name}</span>
                  <span style={{ color: co2Color(e.amount_kg_co2e), fontWeight: 500 }}>
                    {e.amount_kg_co2e.toFixed(3)} kg ({e.quantity} {e.factor.unit})
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  // Resumen general con lista de actividades
  const perActivity = summary.total_activities > 0
    ? (summary.total_kg_co2e / summary.total_activities).toFixed(2)
    : '0'

  const chartData = summary.top_categories.map((c) => ({
    name: c.category.replace(/_/g, ' '),
    kg: parseFloat(c.total_kg_co2e.toFixed(3)),
  }))

  return (
    <div className="summary-panel">
      {/* Botones de filtro de actividades arriba */}
      <div className="activities-tabs" style={{ marginBottom: '24px', paddingBottom: '16px', borderBottom: '1px solid var(--border)' }}>
        <button
          className={`activity-tab ${selectedActivityId === null ? 'activity-tab--active' : ''}`}
          onClick={() => setSelectedActivityId(null)}
          style={{
            padding: '8px 16px',
            marginRight: '8px',
            marginBottom: '8px',
            background: selectedActivityId === null ? 'var(--primary)' : 'var(--surface-2)',
            color: selectedActivityId === null ? 'white' : 'var(--text)',
            border: '1px solid var(--border)',
            borderRadius: '6px',
            cursor: 'pointer',
            fontWeight: selectedActivityId === null ? 500 : 400,
            transition: 'all 0.2s',
          }}
        >
          📊 Resumen General
        </button>

        {activities?.map((activity) => {
          return (
            <button
              key={activity.id}
              className={`activity-tab ${selectedActivityId === activity.id ? 'activity-tab--active' : ''}`}
              onClick={() => setSelectedActivityId(activity.id)}
              style={{
                padding: '8px 16px',
                marginRight: '8px',
                marginBottom: '8px',
                background: selectedActivityId === activity.id ? 'var(--primary)' : 'var(--surface-2)',
                color: selectedActivityId === activity.id ? 'white' : 'var(--text)',
                border: selectedActivityId === activity.id ? '1px solid var(--primary)' : '1px solid var(--border)',
                borderRadius: '6px',
                cursor: 'pointer',
                fontWeight: selectedActivityId === activity.id ? 500 : 400,
                whiteSpace: 'nowrap',
                transition: 'all 0.2s',
              }}
              title={activity.raw_text}
            >
              {activity.main_category}
            </button>
          )
        })}
      </div>

      {/* Contenido del resumen o actividad seleccionada */}
      <div className="stat-grid" style={{ marginBottom: '24px' }}>
        <StatCard label="Total CO₂e" value={summary.total_kg_co2e.toFixed(2)} unit="kg" />
        <StatCard label="Actividades" value={summary.total_activities} />
        <StatCard label="Media/actividad" value={perActivity} unit="kg" />
        <StatCard label="Período" value={summary.period_days} unit="días" />
      </div>

      {chartData.length > 0 && (
        <div className="chart-wrap" style={{ marginBottom: '24px' }}>
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
