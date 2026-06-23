import { useState, useMemo, type CSSProperties } from 'react'
import { useHistory } from '../hooks/useCarbon'
import type { ActivityOut } from '../types'

type ViewMode = 'day' | 'week' | 'month'

interface Props {
  annualGoalKg?: number
}

const CATEGORY_COLORS: Record<string, string> = {
  Alimentación: 'var(--cat-alimentacion)',
  Transporte:   'var(--cat-transporte)',
  Energía:      'var(--cat-energia)',
  Residuos:     'var(--cat-residuos)',
  Compras:      'var(--cat-compras)',
  Ocio:         'var(--cat-ocio)',
}
const DEFAULT_COLOR = 'var(--c-neutral)'

function getBudgets(annualKg: number): Record<ViewMode, number> {
  return {
    day:   annualKg / 365,
    week:  annualKg / 52,
    month: annualKg / 12,
  }
}

const VIEW_LABELS: Record<ViewMode, string> = {
  day: 'Día', week: 'Semana', month: 'Mes',
}

// ── SVG ring ─────────────────────────────────────────────────────────────────

interface RingProps {
  value: number
  max: number
  size: number
  stroke: number
  color: string
  trackColor?: string
  keepColor?: boolean
  children?: React.ReactNode
}

function Ring({ value, max, size, stroke, color, trackColor = 'var(--ring-track)', keepColor = false, children }: RingProps) {
  const r = (size - stroke) / 2
  const circ = 2 * Math.PI * r
  const pct = max > 0 ? Math.min(value / max, 1) : 0
  const over = value > max

  return (
    <svg width={size} height={size} className="ring-svg">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke={trackColor} strokeWidth={stroke} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke={!keepColor && over ? 'var(--c-high)' : color}
        strokeWidth={stroke}
        strokeDasharray={circ}
        strokeDashoffset={circ * (1 - pct)}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        className="ring-progress"
      />
      {children && (
        <foreignObject x={stroke} y={stroke} width={size - stroke * 2} height={size - stroke * 2}>
          <div className="ring-center">
            {children}
          </div>
        </foreignObject>
      )}
    </svg>
  )
}

// ── Date helpers ──────────────────────────────────────────────────────────────

function startOf(mode: ViewMode, date: Date): Date {
  const d = new Date(date)
  if (mode === 'day') { d.setHours(0, 0, 0, 0); return d }
  if (mode === 'week') {
    const day = d.getDay()
    d.setDate(d.getDate() - (day === 0 ? 6 : day - 1))
    d.setHours(0, 0, 0, 0); return d
  }
  d.setDate(1); d.setHours(0, 0, 0, 0); return d
}

function endOf(mode: ViewMode, start: Date): Date {
  const d = new Date(start)
  if (mode === 'day')   { d.setHours(23, 59, 59, 999); return d }
  if (mode === 'week')  { d.setDate(d.getDate() + 6); d.setHours(23, 59, 59, 999); return d }
  d.setMonth(d.getMonth() + 1); d.setDate(0); d.setHours(23, 59, 59, 999); return d
}

function stepDate(mode: ViewMode, date: Date, dir: -1 | 1): Date {
  const d = new Date(date)
  if (mode === 'day')   d.setDate(d.getDate() + dir)
  if (mode === 'week')  d.setDate(d.getDate() + dir * 7)
  if (mode === 'month') d.setMonth(d.getMonth() + dir)
  return d
}

function kgBadgeVars(kg: number): { '--badge-color': string; '--badge-text-color': string } {
  if (kg === 0) return { '--badge-color': 'var(--c-neutral)', '--badge-text-color': 'var(--c-neutral-text)' }
  if (kg <= 1)  return { '--badge-color': 'var(--c-low)',     '--badge-text-color': 'var(--c-low-text)'     }
  if (kg <= 5)  return { '--badge-color': 'var(--c-mid)',     '--badge-text-color': 'var(--c-mid-text)'     }
  return           { '--badge-color': 'var(--c-high)',    '--badge-text-color': 'var(--c-high-text)'    }
}

function formatPeriod(mode: ViewMode, start: Date, end: Date): string {
  const opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' }
  const locale = 'es-ES'
  if (mode === 'day') return start.toLocaleDateString(locale, { weekday: 'long', day: 'numeric', month: 'long' })
  if (mode === 'week') return `${start.toLocaleDateString(locale, opts)} – ${end.toLocaleDateString(locale, opts)}`
  return start.toLocaleDateString(locale, { month: 'long', year: 'numeric' })
}

// ── Main component ────────────────────────────────────────────────────────────

export function DailyDashboard({ annualGoalKg = 6000 }: Props) {
  const { data: activities, isLoading, isError } = useHistory()
  const [mode, setMode] = useState<ViewMode>('day')
  const [anchor, setAnchor] = useState(() => new Date())

  const start = useMemo(() => startOf(mode, anchor), [mode, anchor])
  const end   = useMemo(() => endOf(mode, start),    [mode, start])

  const filtered: ActivityOut[] = useMemo(() => {
    if (!activities) return []
    return activities.filter(a => {
      const t = new Date(a.created_at).getTime()
      return t >= start.getTime() && t <= end.getTime()
    })
  }, [activities, start, end])

  const total = useMemo(
    () => filtered.reduce((s, a) => s + a.emissions.reduce((ss, e) => ss + e.amount_kg_co2e, 0), 0),
    [filtered]
  )

  const byCategory = useMemo(() => {
    const map: Record<string, number> = {}
    for (const a of filtered)
      for (const e of a.emissions)
        map[e.factor.main_category] = (map[e.factor.main_category] ?? 0) + e.amount_kg_co2e
    // Always show all predefined categories; put those with data first
    const allCats = Object.keys(CATEGORY_COLORS)
    return allCats
      .map(cat => [cat, map[cat] ?? 0] as [string, number])
      .sort((a, b) => b[1] - a[1])
  }, [filtered])

  const budget = getBudgets(annualGoalKg)[mode]
  const pctLabel = budget > 0 ? `${Math.min((total / budget) * 100, 999).toFixed(0)}%` : '–'
  const isToday = mode === 'day' && start.toDateString() === new Date().toDateString()
  const isFuture = start > new Date()

  if (isLoading) return <div className="panel-state">Cargando…</div>
  if (isError)   return <div className="panel-state panel-state--error">Error al cargar datos.</div>

  return (
    <div className="dashboard" >

      {/* ── Fixed: rings section ────────────────────────────────────────── */}
      <div className="dashboard__fixed" >
        <div className="dashboard__topbar">
          <div className="dashboard__nav-group" >
            <button className="btn-square grey fs-lg" onClick={() => setAnchor(d => stepDate(mode, d, -1))}>‹</button>

          <h3 className="dashboard__period-label fs-lg">
            {isToday ? 'Hoy' : formatPeriod(mode, start, end)}
          </h3>


            <button className="btn-square grey fs-lg" disabled={isFuture}
              onClick={() => setAnchor(d => stepDate(mode, d, 1))}>›</button>
          </div>

          

          <div className="dashboard__mode-group">
            {(['day', 'week', 'month'] as ViewMode[]).map(m => (
              <button
                key={m}
                className={`btn-square grey${mode === m ? ' btn-square--active' : ''}`}
                onClick={() => { setMode(m); setAnchor(new Date()) }}
              >
                {VIEW_LABELS[m]}
              </button>
            ))}
          </div>
        </div>

        <div className="dashboard__rings-row" >
          <div className="dashboard__ring-wrapper">
            <Ring value={total} max={budget} size={220} stroke={28} color="var(--accent)">
              <div className={`ring-center__value${total > budget ? ' ring-center__value--over' : ''}`}>
                {total.toFixed(2)}
              </div>
              <div className="ring-center__unit">kg CO₂e</div>
              <div className="ring-center__budget">
                {pctLabel} de {budget.toFixed(1)} kg
              </div>
              {filtered.length === 0 && (
                <div className="ring-center__empty">sin actividad</div>
              )}
            </Ring>
          </div>

          <div className="dashboard__categories">
            {byCategory.map(([cat, kg]) => {
              const color = CATEGORY_COLORS[cat] ?? DEFAULT_COLOR
              return (
                <div key={cat} className="dashboard__category-item" style={{ '--cat-color': color } as CSSProperties}>
                  <Ring value={kg} max={budget} size={80} stroke={8} color={color} keepColor>
                    <span className="dashboard__category-value">
                      {kg > 0 ? kg.toFixed(2) : '—'}
                    </span>
                  </Ring>
                  <span className="dashboard__category-name">{cat}</span>
                </div>
              )
            })}
          </div>
        </div>

        {filtered.length > 0 && (
          <h3 className="dashboard__activity-header">Actividades</h3>
        )}
      </div>

      {/* ── Scrollable: activity list ────────────────────────────────────── */}
      <div className="dashboard__scroll">
        {filtered.length > 0 ? (
          <div className="dashboard__activity-list">
            {filtered.map(a => {
              const kg = a.emissions.reduce((s, e) => s + e.amount_kg_co2e, 0)
              return (
                <div key={a.id} className="dashboard__activity-row">
                  <p className="dashboard__activity-text">
                    <span className="dashboard__activity-cat">{a.main_category}</span>
                    <span className="dashboard__activity-sep"> | </span>
                    {a.raw_text.length > 80 ? a.raw_text.slice(0, 80) + '…' : a.raw_text}
                  </p>
                  <span className="co2-badge" style={kgBadgeVars(kg) as CSSProperties}>
                    {kg.toFixed(3)} kg
                  </span>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="dashboard__empty">
            No hay actividades registradas para este período.
          </div>
        )}
      </div>
    </div>
  )
}
