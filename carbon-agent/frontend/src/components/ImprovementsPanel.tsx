import { useImprovements } from '../hooks/useCarbon'
import type { ImprovementSuggestion } from '../types'

interface Props {
  userId?: string
  annualGoalKg?: number
}

const CATEGORY_ICONS: Record<string, string> = {
  Alimentación: '🥗',
  Transporte: '🚗',
  Energía: '⚡',
  Residuos: '♻️',
  Compras: '🛍️',
  Ocio: '🎭',
}

const IMPACT_COLOR = (pct: number) =>
  pct >= 40 ? '#ef4444' : pct >= 20 ? '#fb923c' : '#facc15'

function SuggestionCard({ s }: { s: ImprovementSuggestion }) {
  const icon = CATEGORY_ICONS[s.category] ?? '🌿'
  const saving = Math.round(s.current_kg * s.potential_saving_pct / 100)

  return (
    <div style={{
      background: 'var(--surface-2)',
      border: '1px solid var(--border)',
      borderRadius: '12px',
      padding: '20px',
      marginBottom: '16px',
    }}>
      {/* Cabecera */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '22px' }}>{icon}</span>
          <div>
            <span style={{ fontWeight: 600, fontSize: '14px' }}>{s.category}</span>
            <span style={{
              marginLeft: '10px',
              fontSize: '12px',
              color: IMPACT_COLOR(s.pct_of_total),
              fontWeight: 500,
            }}>
              {s.current_kg.toFixed(2)} kg · {s.pct_of_total.toFixed(0)}% del total
            </span>
          </div>
        </div>
        <div style={{
          background: '#166534',
          color: '#4ade80',
          borderRadius: '20px',
          padding: '3px 10px',
          fontSize: '12px',
          fontWeight: 600,
          whiteSpace: 'nowrap',
        }}>
          −{s.potential_saving_pct}% · ahorra ~{saving} kg
        </div>
      </div>

      {/* Barra de impacto */}
      <div style={{ background: 'var(--border)', borderRadius: '4px', height: '4px', marginBottom: '14px' }}>
        <div style={{
          width: `${Math.min(s.pct_of_total, 100)}%`,
          height: '100%',
          background: IMPACT_COLOR(s.pct_of_total),
          borderRadius: '4px',
        }} />
      </div>

      {/* Acción principal */}
      <p style={{ fontSize: '14px', fontWeight: 500, marginBottom: '8px', color: 'var(--text)' }}>
        {s.action}
      </p>

      {/* Consejo adicional */}
      <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.5', margin: 0 }}>
        {s.tip}
      </p>
    </div>
  )
}

export function ImprovementsPanel({ userId = 'default', annualGoalKg = 6000 }: Props) {
  const { data, isLoading, isError, refetch, isFetching } = useImprovements(userId, annualGoalKg)

  if (isLoading || isFetching) return (
    <div className="panel-state">
      <span className="panel-state__icon">🤖</span>
      <p>Analizando tu huella de carbono…</p>
    </div>
  )

  if (isError) return (
    <div className="panel-state panel-state--error">Error al generar sugerencias.</div>
  )

  if (!data || data.suggestions.length === 0) return (
    <div className="panel-state">
      <span className="panel-state__icon">🌱</span>
      <p>Sin datos suficientes aún.</p>
      <p className="panel-state__hint">Registra algunas actividades para recibir sugerencias personalizadas.</p>
    </div>
  )

  const overBudget = data.total_kg > data.budget_kg
  const gap = Math.abs(data.total_kg - data.budget_kg).toFixed(1)

  return (
    <div className="summary-panel">
      {/* Contexto */}
      <div style={{
        background: overBudget ? 'rgba(239,68,68,0.1)' : 'rgba(74,222,128,0.1)',
        border: `1px solid ${overBudget ? '#ef4444' : '#4ade80'}`,
        borderRadius: '10px',
        padding: '14px 18px',
        marginBottom: '24px',
        fontSize: '13px',
        lineHeight: '1.6',
      }}>
        {overBudget
          ? `⚠️ Estás ${gap} kg por encima del presupuesto sostenible de ${data.budget_kg.toFixed(0)} kg/mes. Aquí tienes las áreas donde reducir más impacto:`
          : `✅ Estás dentro del presupuesto sostenible (${data.total_kg.toFixed(1)} kg de ${data.budget_kg.toFixed(0)} kg). Sigue mejorando con estos consejos:`
        }
      </div>

      {/* Sugerencias */}
      {data.suggestions.map((s, i) => (
        <SuggestionCard key={i} s={s} />
      ))}

      {/* Botón regenerar */}
      <button
        onClick={() => refetch()}
        style={{
          marginTop: '8px',
          padding: '10px 20px',
          background: 'var(--surface-2)',
          border: '1px solid var(--border)',
          borderRadius: '8px',
          cursor: 'pointer',
          fontSize: '13px',
          color: 'var(--text-muted)',
          width: '100%',
        }}
      >
        🔄 Regenerar sugerencias
      </button>
    </div>
  )
}
