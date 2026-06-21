import { useState, useEffect, type CSSProperties, type ReactNode } from 'react'
import { Target, User, UtensilsCrossed, Thermometer, Sun, Moon } from 'lucide-react'
import { useSettings } from '../hooks/useSettings'
import { useProfile, useUpdateProfile, usePortions, useUpdatePortions, useRecurring, useUpdateRecurring } from '../hooks/useCarbon'
import type { RecurringActivity } from '../types'

// ── Sub-panel: Objetivo CO₂ ───────────────────────────────────────────────────

const cssVar = (v: string) => getComputedStyle(document.documentElement).getPropertyValue(v).trim()

const LEVELS = [
  {
    t: 2,
    label: '2 t — Óptimo climático',
    color: cssVar('--c-success'),
    temp: '+1,5 °C',
    tempColor: cssVar('--c-success'),
    desc: 'El objetivo del Acuerdo de París para limitar el calentamiento global a 1,5 °C. Requiere un cambio profundo de hábitos: dieta mayoritariamente vegetal, transporte público o bicicleta, cero vuelos, hogar eficiente. Es el nivel de un ciudadano comprometido con la sostenibilidad.',
  },
  {
    t: 4,
    label: '4 t — Avanzado',
    color: cssVar('--c-level-adv'),
    temp: '+1,7 °C',
    tempColor: cssVar('--c-level-adv'),
    desc: 'Por debajo de la media europea. Compatible con los objetivos climáticos de 2 °C si se mantiene. Implica reducir significativamente la carne roja, usar transporte bajo en carbono la mayoría del tiempo y limitar los vuelos de corta distancia.',
  },
  {
    t: 6,
    label: '6 t — Media europea',
    color: cssVar('--cat-energia'),
    temp: '+2,0 °C',
    tempColor: cssVar('--cat-energia'),
    desc: 'Aproximadamente la media de España y el sur de Europa (~7 t/año). Supone ya un esfuerzo notable de reducción respecto a la media global de países ricos. Es un buen punto de partida si estás empezando a medir tu huella.',
  },
  {
    t: 8,
    label: '8 t — Media países desarrollados',
    color: cssVar('--c-danger'),
    temp: '+2,5 °C',
    tempColor: cssVar('--c-danger'),
    desc: 'La huella media de ciudadanos de países de renta alta (Europa occidental, EE.UU., Australia). Mantener este nivel contribuye a un calentamiento global de 2,5 °C o más, con consecuencias severas: más sequías, inundaciones y pérdida de biodiversidad.',
  },
]

function getLevelInfo(t: number) {
  const exact = LEVELS.find(l => l.t === t)
  if (exact) return exact
  if (t < 4) return LEVELS[0]
  if (t < 6) return LEVELS[1]
  if (t < 8) return LEVELS[2]
  return LEVELS[3]
}

function GoalPanel() {
  const { settings, update } = useSettings()
  const t = settings.annualGoalTonnes
  const level = getLevelInfo(t)
  const monthlyKg = Math.round(t * 1000 / 12)
  const dailyKg = (t * 1000 / 365).toFixed(1)

  return (
    <div className="goal-layout">
      {/* Top: full-width context card */}
      <div className="card">
        <h2>¿Qué es la huella de carbono?</h2>
        <p>
          La huella de carbono mide la cantidad de gases de efecto invernadero (CO₂ y equivalentes) que generamos con nuestras actividades diarias: lo que comemos, cómo nos desplazamos, la energía que consumimos o lo que compramos.
        </p>
        <p>
          Cuanto más alta sea tu meta anual, menor presión sentirás al principio — pero mayor será tu impacto en el clima. La ciencia indica que para limitar el calentamiento a <strong>1,5 °C</strong> necesitamos reducir a <strong>~2 t/persona/año</strong> antes de 2050. Empieza donde puedas y ve bajando poco a poco.
        </p>
      </div>

      {/* Bottom row: slider (2/3) + level info (1/3) */}
      <div className="goal-layout__top">
        <div className="card" style={{ '--level-color': level.color } as CSSProperties}>
          <div className="settings__card-header">
            <div>
              <h2>Meta anual</h2>
              <p className="settings__goal-value">
                {t} t
                <span>CO₂/año</span>
              </p>
            </div>
            <div>
              <div className="text-end">equivale a</div>
              <div>
                <strong>{monthlyKg} kg</strong>
                <span>/mes · </span>
                <strong>{dailyKg} kg</strong>
                <span>/día</span>
              </div>
            </div>
          </div>

          <div>
            <input
              type="range"
              min={2} max={8} step={1}
              value={t}
              onChange={e => update({ annualGoalTonnes: Number(e.target.value) })}
              className="settings__slider"
            />
          </div>

          <div className="settings__ticks">
            {[2, 3, 4, 5, 6, 7, 8].map(v => (
              <span key={v} className={v === t ? 'settings__tick--active' : 'settings__tick'}>
                {v}t
              </span>
            ))}
          </div>

          <div className="settings__level-btns">
            {LEVELS.map(l => (
              <button
                key={l.t}
                onClick={() => update({ annualGoalTonnes: l.t })}
                className={`settings__level-btn ${t === l.t ? 'settings__level-btn--active' : ''}`}
                style={{ '--level-color': l.color } as CSSProperties}
              >
                {l.t} t
              </button>
            ))}
          </div>
        </div>

        <div className="card" style={{ '--level-color': level.color, '--temp-color': level.tempColor } as CSSProperties}>
          <div className="settings__info-header">
            <h2>{level.label}</h2>
            <span className="settings__temp-badge"><Thermometer size={14} className="icon" />{level.temp}</span>
          </div>
          <p>{level.desc}</p>
        </div>
      </div>
    </div>
  )
}

// ── Sub-panel: Preferencias de usuario ───────────────────────────────────────

function ProfilePanel() {
  const { data: profile, isLoading } = useProfile()
  const { mutate: save, isPending: isSaving } = useUpdateProfile()
  const [saved, setSaved] = useState(false)

  const [displayName, setDisplayName] = useState('')
  const [homeCity, setHomeCity]       = useState('')
  const [workPlace, setWorkPlace]     = useState('')

  useEffect(() => {
    if (profile) {
      setDisplayName(profile.display_name ?? '')
      setHomeCity(profile.home_city ?? '')
      setWorkPlace(profile.work_place ?? '')
    }
  }, [profile])

  useEffect(() => {
    if (!saved) return
    const t = setTimeout(() => setSaved(false), 5000)
    return () => clearTimeout(t)
  }, [saved])

  const handleSave = () => {
    save({
      display_name: displayName.trim() || null,
      home_city:    homeCity.trim()    || null,
      work_place:   workPlace.trim()   || null,
    }, { onSuccess: () => setSaved(true) })
  }

  if (isLoading) return <p>Cargando perfil…</p>

  return (
    <div className="settings__profile">
      <div className="card">
        <h2>¿Para qué sirve esto?</h2>
        <p>
          Al guardar tu ciudad y lugar de trabajo, el asistente podrá calcular automáticamente
          las distancias de tus desplazamientos sin preguntarte cada vez.
        </p>
      </div>

      <form onSubmit={e => { e.preventDefault(); handleSave() }}>
        <div className="settings__profile-fields">
          <label className="form__field">
            <span>Tu nombre</span>
            <input
              type="text"
              placeholder="ej: Ana"
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
            />
          </label>

          <label className="form__field">
            <span>Mi dirección</span>
            <input
              type="text"
              placeholder="ej: Barcelona"
              value={homeCity}
              onChange={e => setHomeCity(e.target.value)}
            />
            <span className='help-text'>Se usa como origen por defecto en tus viajes desde casa.</span>
          </label>

          <label className="form__field">
            <span>Mi trabajo / centro de estudios</span>
            <input
              type="text"
              placeholder="ej: Oficina en Madrid, Universidad de Valencia"
              value={workPlace}
              onChange={e => setWorkPlace(e.target.value)}
            />
            <span className='help-text'>Permite calcular tu huella de trayectos al trabajo.</span>
          </label>
        </div>

        <div className="text-end">
          {saved && <span className="settings__save-ok">Guardado</span>}
          <button type="submit" disabled={isSaving}>
            {isSaving ? 'Guardando…' : 'Guardar preferencias'}
          </button>
          
        </div>
      </form>
    </div>
  )
}

// ── Sub-panel: Porciones por defecto ─────────────────────────────────────────


function parseInput(unit: string, raw: string): number | null {
  const n = parseFloat(raw.replace(',', '.'))
  if (isNaN(n) || n <= 0) return null
  if (unit === 'kg') return n / 1000
  if (unit === 'litro') return n / 1000
  return n
}

function inputUnit(unit: string): string {
  if (unit === 'kg') return 'gramos'
  if (unit === 'litro') return 'ml'
  return unit
}

function toInputValue(unit: string, qty: number): string {
  if (unit === 'kg') return String(Math.round(qty * 1000))
  if (unit === 'litro') return String(Math.round(qty * 1000))
  return String(qty)
}

function PortionsPanel() {
  const { data: portions, isLoading } = usePortions()
  const { mutate: save, isPending: isSaving } = useUpdatePortions()
  const [edits, setEdits] = useState<Record<string, string>>({})
  const [saved, setSaved] = useState(false)
  const [activeCategory, setActiveCategory] = useState<string>('all')

  useEffect(() => {
    if (!saved) return
    const t = setTimeout(() => setSaved(false), 5000)
    return () => clearTimeout(t)
  }, [saved])

  if (isLoading) return <p>Cargando porciones…</p>

  const categories = ['all', ...Array.from(new Set(portions?.map(p => p.main_category) ?? []))]
  const visible = activeCategory === 'all' ? portions : portions?.filter(p => p.main_category === activeCategory)
  const countFor = (cat: string) => cat === 'all' ? (portions?.length ?? 0) : (portions?.filter(p => p.main_category === cat).length ?? 0)

  const handleChange = (category: string, value: string) => {
    setEdits(prev => ({ ...prev, [category]: value }))
    setSaved(false)
  }

  const handleReset = (category: string) => {
    setEdits(prev => { const next = { ...prev }; delete next[category]; return next })
    setSaved(false)
  }

  const handleSave = () => {
    if (!portions) return
    const updates: Record<string, number> = {}
    for (const entry of portions) {
      const raw = edits[entry.category]
      if (raw !== undefined) {
        const parsed = parseInput(entry.unit, raw)
        if (parsed !== null) updates[entry.category] = parsed
      }
    }
    save(updates, { onSuccess: () => { setEdits({}); setSaved(true) } })
  }

  const handleStep = (category: string, current: string, delta: number) => {
    const n = parseFloat(current.replace(',', '.')) || 0
    handleChange(category, String(Math.max(1, n + delta)))
  }

  return (
    <form className="settings__profile" onSubmit={e => { e.preventDefault(); handleSave() }}>
      <div className="card card--spaced">
        <h2>¿Para qué sirve esto?</h2>
        <p>
          Cuando dices "he comido pollo" sin indicar gramos, el asistente usa estas cantidades por defecto.
          Ajústalas a tus raciones habituales para obtener estimaciones más precisas.
        </p>
      </div>

      <div className="admin-tabs">
        {categories.map(cat => (
          <button
            key={cat}
            type="button"
            className={`btn-square ${activeCategory === cat ? 'btn-square--active' : ''}`}
            onClick={() => setActiveCategory(cat)}
          >
            {cat === 'all' ? 'Todas' : cat} ({countFor(cat)})
          </button>
        ))}
      </div>

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Alimento</th>
              <th>Porción por defecto</th>
              <th>Tu porción</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {visible?.map(entry => {
              const effective = entry.user_quantity ?? entry.default_quantity
              const rawEdit = edits[entry.category]
              const displayValue = rawEdit !== undefined ? rawEdit : toInputValue(entry.unit, effective)
              const isCustom = entry.user_quantity !== null && entry.user_quantity !== undefined
              const canReset = isCustom || rawEdit !== undefined

              return (
                <tr key={entry.category} className="admin-table__row">
                  <td className="admin-table__term">{entry.display_name}</td>
                  <td className="admin-table__num">{toInputValue(entry.unit, entry.default_quantity)} {inputUnit(entry.unit)}</td>
                  <td>
                    <div className="settings__portion-input-wrap">
                      <button className="settings__portion-step" type="button" onClick={() => handleStep(entry.category, displayValue, -1)}>−</button>
                      <input
                        className="settings__portion-input"
                        type="number"
                        min={1}
                        value={displayValue}
                        onChange={e => handleChange(entry.category, e.target.value)}
                      />
                      <button className="settings__portion-step" type="button" onClick={() => handleStep(entry.category, displayValue, 1)}>+</button>
                      <span className="settings__portion-unit">{inputUnit(entry.unit)}</span>
                    </div>
                  </td>
                  <td>
                    <button
                      className="settings__portion-reset"
                      type="button"
                      title="Restaurar por defecto"
                      disabled={!canReset}
                      style={{ opacity: canReset ? 1 : 0.25 }}
                      onClick={() => {
                        if (rawEdit !== undefined) handleReset(entry.category)
                        if (isCustom) save({ [entry.category]: entry.default_quantity }, { onSuccess: () => setSaved(true) })
                      }}
                    >↺</button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="text-end mb-16">        
        {saved && <span className="settings__save-ok">Guardado</span>}
        <button type="submit" disabled={isSaving || Object.keys(edits).length === 0}>
          {isSaving ? 'Guardando…' : 'Guardar porciones'}
        </button>
        
      </div>
    </form>
  )
}

// ── Sub-panel: Rutina diaria ──────────────────────────────────────────────────

function RecurringPanel() {
  const { data: items = [], isLoading, isError } = useRecurring()
  const { mutate: save, isPending: isSaving } = useUpdateRecurring()
  const [local, setLocal] = useState<RecurringActivity[]>([])
  const [saved, setSaved] = useState(false)

  useEffect(() => { if (items.length) setLocal(items) }, [items])

  useEffect(() => {
    if (!saved) return
    const t = setTimeout(() => setSaved(false), 5000)
    return () => clearTimeout(t)
  }, [saved])

  const toggle = (cat: string) =>
    setLocal(prev => prev.map(i => i.category === cat ? { ...i, enabled: !i.enabled } : i))

  const setQty = (cat: string, qty: number) =>
    setLocal(prev => prev.map(i => i.category === cat ? { ...i, quantity: Math.max(0.1, qty) } : i))

  const handleSave = () => save(local, { onSuccess: () => setSaved(true) })

  if (isLoading) return <p>Cargando rutina…</p>
  if (isError) return <p>No se pudo cargar la rutina diaria.</p>

  return (
    <div className="settings__profile">
      <div className="card mt-3">
        <h2>Consumo diario automático</h2>
        <p>
          Activa los elementos que forman parte de tu día a día. Cada vez que abras la app,
          se registrarán automáticamente si aún no se han contabilizado hoy.
        </p>
      </div>

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Activo</th>
              <th>Actividad</th>
              <th>Cantidad diaria</th>
              <th>Unidad</th>
              <th>CO₂/día</th>
            </tr>
          </thead>
          <tbody>
            {local.map(item => (
              <tr key={item.category} className="admin-table__row">
                <td>
                  <input
                    type="checkbox"
                    checked={item.enabled}
                    onChange={() => toggle(item.category)}
                  />
                </td>
                <td className="admin-table__term">
                  {item.display_name}
                  {item.hint && <span className="help-text">{item.hint}</span>}
                </td>
                <td>
                  <div className="settings__portion-input-wrap">
                    <button className="settings__portion-step" type="button" onClick={() => setQty(item.category, item.quantity - 1)}>−</button>
                    <input
                      className="settings__portion-input"
                      type="number"
                      min={0.1}
                      step={0.5}
                      value={item.quantity}
                      onChange={e => setQty(item.category, parseFloat(e.target.value) || 0)}
                    />
                    <button className="settings__portion-step" type="button" onClick={() => setQty(item.category, item.quantity + 1)}>+</button>
                  </div>
                </td>
                <td className="admin-table__cat">{item.unit}</td>
                <td className="admin-table__num">
                  {((item.factor_kg_co2e ?? 0) * item.quantity * 1000).toFixed(1)} g
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="text-end">
        {saved && <span className="settings__save-ok">Guardado</span>}
        <button onClick={handleSave} disabled={isSaving}>
          {isSaving ? 'Guardando…' : 'Guardar rutina'}
        </button>
      </div>
    </div>
  )
}

// ── Panel principal ───────────────────────────────────────────────────────────

export type SettingsSubTab = 'goal' | 'profile' | 'portions'

const SUB_ICON_PROPS = { size: 15, className: 'icon icon-nav' }

export const SETTINGS_SUBTABS: { id: SettingsSubTab; label: string; icon: ReactNode }[] = [
  { id: 'goal',     label: 'Objetivo CO₂', icon: <Target          {...SUB_ICON_PROPS} /> },
  { id: 'profile',  label: 'Preferencias', icon: <User            {...SUB_ICON_PROPS} /> },
  { id: 'portions', label: 'Porciones',    icon: <UtensilsCrossed {...SUB_ICON_PROPS} /> },
]

interface SettingsPanelProps {
  tab: SettingsSubTab
  lightTheme: boolean
  onToggleTheme: () => void
}

export function SettingsPanel({ tab, lightTheme, onToggleTheme }: SettingsPanelProps) {
  return (
    <div className="settings">
      {tab === 'goal'     && <GoalPanel />}
      {tab === 'profile'  && (
        <>
          <ProfilePanel />
          <RecurringPanel />
          <div className="settings__theme-row">
            <span>Tema</span>
            <button className="contrast-toggle" onClick={onToggleTheme}>
              {lightTheme ? <Moon size={15} className="icon" /> : <Sun size={15} className="icon" />}
              {lightTheme ? 'Cambiar a oscuro' : 'Cambiar a claro'}
            </button>
          </div>
        </>
      )}
      {tab === 'portions' && <PortionsPanel />}
    </div>
  )
}
