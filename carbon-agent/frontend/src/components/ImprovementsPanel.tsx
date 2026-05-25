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

function CategoryGroup({ suggestions }: { suggestions: ImprovementSuggestion[] }) {
  const first = suggestions[0]
  const icon = CATEGORY_ICONS[first.category] ?? '🌿'
  const color = IMPACT_COLOR(first.pct_of_total)

  return (
    <div className="suggestion-card">
      <div className="suggestion-card__header">
        <div className="suggestion-card__title-group">
          <span className="suggestion-card__icon">{icon}</span>
          <div>
            <span className="suggestion-card__category">{first.category}</span>
            <span className="suggestion-card__stats" style={{ color }}>
              {first.current_kg.toFixed(2)} kg · {first.pct_of_total.toFixed(0)}% del total
            </span>
          </div>
        </div>
      </div>

      <div className="suggestion-card__bar">
        <div
          className="suggestion-card__bar-fill"
          style={{ width: `${Math.min(first.pct_of_total, 100)}%`, background: color }}
        />
      </div>

      {suggestions.map((s, i) => {
        const saving = Math.round(s.current_kg * s.potential_saving_pct / 100)
        return (
          <div key={i} className="suggestion-card__item">
            <div className="suggestion-card__item-header">
              <p className="suggestion-card__action">{s.action}</p>
              <span className="suggestion-card__badge">
                −{s.potential_saving_pct}% · ahorra ~{saving} kg
              </span>
            </div>
            <p className="suggestion-card__tip">{s.tip}</p>
          </div>
        )
      })}
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

  const grouped = data.suggestions.reduce((map, s) => {
    if (!map.has(s.category)) map.set(s.category, [])
    map.get(s.category)!.push(s)
    return map
  }, new Map<string, ImprovementSuggestion[]>())

  return (
    <div className="summary-panel">
      <div
        className="suggestions-context"
        style={{
          background: overBudget ? 'rgba(239,68,68,0.1)' : 'rgba(74,222,128,0.1)',
          border: `1px solid ${overBudget ? '#ef4444' : '#4ade80'}`,
        }}
      >
        {overBudget
          ? `⚠️ Estás ${gap} kg por encima del presupuesto sostenible de ${data.budget_kg.toFixed(0)} kg/mes. Aquí tienes las áreas donde reducir más impacto:`
          : `✅ Estás dentro del presupuesto sostenible (${data.total_kg.toFixed(1)} kg de ${data.budget_kg.toFixed(0)} kg). Sigue mejorando con estos consejos:`
        }
      </div>

      {Array.from(grouped.entries()).map(([category, suggestions]) => (
        <CategoryGroup key={category} suggestions={suggestions} />
      ))}

      <button className="suggestions-regen-btn" onClick={() => refetch()}>
        🔄 Regenerar sugerencias
      </button>
    </div>
  )
}
