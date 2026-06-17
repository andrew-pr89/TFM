import type { CSSProperties } from 'react'
import { RefreshCw, Utensils, Car, Zap, Recycle, ShoppingBag, Music, Leaf, type LucideIcon } from 'lucide-react'
import { useImprovements } from '../hooks/useCarbon'
import type { ImprovementSuggestion } from '../types'

interface Props {
  annualGoalKg?: number
}

interface CategoryConfig { icon: LucideIcon; colorVar: string }

const CATEGORY_CONFIG: Record<string, CategoryConfig> = {
  Alimentación: { icon: Utensils,    colorVar: 'var(--cat-alimentacion)' },
  Transporte:   { icon: Car,         colorVar: 'var(--cat-transporte)'   },
  Energía:      { icon: Zap,         colorVar: 'var(--cat-energia)'      },
  Residuos:     { icon: Recycle,     colorVar: 'var(--cat-residuos)'     },
  Compras:      { icon: ShoppingBag, colorVar: 'var(--cat-compras)'      },
  Ocio:         { icon: Music,       colorVar: 'var(--cat-ocio)'         },
}

function CategoryIconBadge({ category }: { category: string }) {
  const cfg = CATEGORY_CONFIG[category]
  const Icon = cfg?.icon ?? Leaf
  const color = cfg?.colorVar ?? 'var(--c-neutral)'
  return (
    <span
      className="cat-icon-badge"
      style={{ '--cat-icon-color': color } as CSSProperties}
    >
      <Icon size={15} strokeWidth={1.5} />
    </span>
  )
}

const IMPACT_COLOR = (pct: number) =>
  pct >= 40 ? 'var(--c-high)' : pct >= 20 ? 'var(--c-mid)' : 'var(--c-neutral)'

function CategoryGroup({ suggestions }: { suggestions: ImprovementSuggestion[] }) {
  const first = suggestions[0]
  const color = IMPACT_COLOR(first.pct_of_total)

  return (
    <div className="suggestion-card" style={{ '--impact-color': color } as CSSProperties}>
      <div className="suggestion-card__header">
        <div className="suggestion-card__title-group">
          <CategoryIconBadge category={first.category} />
          <div>
            <span className="suggestion-card__category">{first.category}</span>
            <span className="suggestion-card__stats">
              {first.current_kg.toFixed(2)} kg · {first.pct_of_total.toFixed(0)}% del total
            </span>
          </div>
        </div>
      </div>

      <div className="suggestion-card__bar">
        <div
          className="suggestion-card__bar-fill"
          style={{ width: `${Math.min(first.pct_of_total, 100)}%` }}
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

export function ImprovementsPanel({ annualGoalKg = 6000 }: Props) {
  const { data, isLoading, isError, refetch, isFetching } = useImprovements(annualGoalKg)

  if (isLoading || isFetching) return (
    <div className="panel-state">
      <span className="spinner" />
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
      <div className={`suggestions-context ${overBudget ? 'suggestions-context--over' : 'suggestions-context--ok'}`}>
        {overBudget
          ? `Estás ${gap} kg por encima del presupuesto sostenible de ${data.budget_kg.toFixed(0)} kg/mes. Aquí tienes las áreas donde reducir más impacto:`
          : `Estás dentro del presupuesto sostenible (${data.total_kg.toFixed(1)} kg de ${data.budget_kg.toFixed(0)} kg). Sigue mejorando con estos consejos:`
        }
      </div>

      {Array.from(grouped.entries()).map(([category, suggestions]) => (
        <CategoryGroup key={category} suggestions={suggestions} />
      ))}

      <button className="btn-solid suggestions-regen-btn" onClick={() => refetch()}>
        <RefreshCw size={15} strokeWidth={1.5} />
        Regenerar sugerencias
      </button>
    </div>
  )
}
