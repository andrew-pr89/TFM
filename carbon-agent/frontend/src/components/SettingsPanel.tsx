import { useState, useEffect, type CSSProperties, type ReactNode } from 'react'
import { Target, User, UtensilsCrossed } from 'lucide-react'
import { useSettings } from '../hooks/useSettings'
import { useProfile, useUpdateProfile, usePortions, useUpdatePortions } from '../hooks/useCarbon'

// ── Sub-panel: Objetivo CO₂ ───────────────────────────────────────────────────

const LEVELS = [
  {
    t: 2,
    label: '2 t — Óptimo climático',
    color: '#4ade80',
    temp: '+1,5 °C',
    tempColor: '#4ade80',
    desc: 'El objetivo del Acuerdo de París para limitar el calentamiento global a 1,5 °C. Requiere un cambio profundo de hábitos: dieta mayoritariamente vegetal, transporte público o bicicleta, cero vuelos, hogar eficiente. Es el nivel de un ciudadano comprometido con la sostenibilidad.',
  },
  {
    t: 4,
    label: '4 t — Avanzado',
    color: '#a3e635',
    temp: '+1,7 °C',
    tempColor: '#a3e635',
    desc: 'Por debajo de la media europea. Compatible con los objetivos climáticos de 2 °C si se mantiene. Implica reducir significativamente la carne roja, usar transporte bajo en carbono la mayoría del tiempo y limitar los vuelos de corta distancia.',
  },
  {
    t: 6,
    label: '6 t — Media europea',
    color: '#facc15',
    temp: '+2,0 °C',
    tempColor: '#facc15',
    desc: 'Aproximadamente la media de España y el sur de Europa (~7 t/año). Supone ya un esfuerzo notable de reducción respecto a la media global de países ricos. Es un buen punto de partida si estás empezando a medir tu huella.',
  },
  {
    t: 8,
    label: '8 t — Media países desarrollados',
    color: '#ef4444',
    temp: '+2,5 °C',
    tempColor: '#ef4444',
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
      {/* Top row: slider (2/3) + level info (1/3) */}
      <div className="goal-layout__top">
        <div className="settings__card" style={{ '--level-color': level.color } as CSSProperties}>
          <div className="settings__card-header">
            <div>
              <p className="settings__goal-label">META ANUAL</p>
              <p className="settings__goal-value settings__goal-value--level">
                {t} t
                <span className="settings__goal-unit">CO₂/año</span>
              </p>
            </div>
            <div className="settings__goal-equiv">
              <div className="settings__equiv-label">equivale a</div>
              <div className="settings__equiv-values">
                <span className="settings__equiv-value--level">{monthlyKg} kg</span>
                <span className="settings__equiv-value--muted">/mes · </span>
                <span className="settings__equiv-value--level">{dailyKg} kg</span>
                <span className="settings__equiv-value--muted">/día</span>
              </div>
            </div>
          </div>

          <div className="settings__slider-wrap">
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

        <div className="settings__info-card" style={{ '--level-color': level.color, '--temp-color': level.tempColor } as CSSProperties}>
          <div className="settings__info-header">
            <span className="settings__info-name">{level.label}</span>
            <span className="settings__temp-badge">🌡️ {level.temp}</span>
          </div>
          <p className="settings__info-desc">{level.desc}</p>
        </div>
      </div>

      {/* Bottom row: full-width context card with image */}
      <div className="settings__context-box settings__context-box--brand goal-layout__bottom">
        <div className="goal-context__img-placeholder">
          <span className="goal-context__img-label">📷 Imagen ilustrativa</span>
        </div>
        <div className="goal-context__text">
          <p className="settings__context-title">¿Qué es la huella de carbono?</p>
          <p className="settings__context-desc">
            La huella de carbono mide la cantidad de gases de efecto invernadero (CO₂ y equivalentes) que generamos con nuestras actividades diarias: lo que comemos, cómo nos desplazamos, la energía que consumimos o lo que compramos.
          </p>
          <p className="settings__context-desc">
            Cuanto más alta sea tu meta anual, menor presión sentirás al principio — pero mayor será tu impacto en el clima. La ciencia indica que para limitar el calentamiento a <strong>1,5 °C</strong> necesitamos reducir a <strong>~2 t/persona/año</strong> antes de 2050. Empieza donde puedas y ve bajando poco a poco.
          </p>
        </div>
      </div>
    </div>
  )
}

// ── Sub-panel: Preferencias de usuario ───────────────────────────────────────

function ProfilePanel() {
  const { data: profile, isLoading } = useProfile()
  const { mutate: save, isPending: isSaving, isSuccess } = useUpdateProfile()

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

  const handleSave = () => {
    save({
      display_name: displayName.trim() || null,
      home_city:    homeCity.trim()    || null,
      work_place:   workPlace.trim()   || null,
    })
  }

  if (isLoading) return <p className="settings__context-desc">Cargando perfil…</p>

  return (
    <div className="settings__profile">
      <div className="settings__context-box settings__context-box--tight">
        <p className="settings__context-title">¿Para qué sirve esto?</p>
        <p className="settings__context-desc">
          Al guardar tu ciudad y lugar de trabajo, el asistente podrá calcular automáticamente
          las distancias de tus desplazamientos sin preguntarte cada vez.
        </p>
      </div>

      <div className="settings__profile-fields">
        <label className="settings__field">
          <span className="settings__field-label">Tu nombre (opcional)</span>
          <input
            className="settings__field-input"
            type="text"
            placeholder="ej: Ana"
            value={displayName}
            onChange={e => setDisplayName(e.target.value)}
          />
        </label>

        <label className="settings__field">
          <span className="settings__field-label">Mi ciudad</span>
          <input
            className="settings__field-input"
            type="text"
            placeholder="ej: Barcelona"
            value={homeCity}
            onChange={e => setHomeCity(e.target.value)}
          />
          <span className="settings__field-hint">
            Se usa como origen por defecto en tus viajes desde casa.
          </span>
        </label>

        <label className="settings__field">
          <span className="settings__field-label">Mi trabajo / centro de estudios</span>
          <input
            className="settings__field-input"
            type="text"
            placeholder="ej: Oficina en Madrid, Universidad de Valencia"
            value={workPlace}
            onChange={e => setWorkPlace(e.target.value)}
          />
          <span className="settings__field-hint">
            Permite calcular tu huella de trayectos al trabajo.
          </span>
        </label>
      </div>

      <div className="settings__profile-actions">
        <button
          className="settings__save-btn"
          onClick={handleSave}
          disabled={isSaving}
        >
          {isSaving ? 'Guardando…' : 'Guardar preferencias'}
        </button>
        {isSuccess && <span className="settings__save-ok">Guardado</span>}
      </div>
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

  if (isLoading) return <p className="settings__context-desc">Cargando porciones…</p>

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

  return (
    <div className="settings__profile">
      <div className="settings__context-box settings__context-box--spaced">
        <p className="settings__context-title">¿Para qué sirve esto?</p>
        <p className="settings__context-desc">
          Cuando dices "he comido pollo" sin indicar gramos, el asistente usa estas cantidades por defecto.
          Ajústalas a tus raciones habituales para obtener estimaciones más precisas.
        </p>
      </div>

      <div className="settings__portions-list">
        {portions?.map(entry => {
          const effective = entry.user_quantity ?? entry.default_quantity
          const rawEdit = edits[entry.category]
          const displayValue = rawEdit !== undefined
            ? rawEdit
            : toInputValue(entry.unit, effective)
          const isCustom = entry.user_quantity !== null && entry.user_quantity !== undefined

          return (
            <div key={entry.category} className="settings__portion-row">
              <span className="settings__portion-name">{entry.display_name}</span>
              <div className="settings__portion-input-wrap">
                <input
                  className="settings__portion-input"
                  type="number"
                  min={1}
                  value={displayValue}
                  onChange={e => handleChange(entry.category, e.target.value)}
                />
                <span className="settings__portion-unit">{inputUnit(entry.unit)}</span>
                {isCustom && rawEdit === undefined && (
                  <button
                    className="settings__portion-reset"
                    title="Restaurar por defecto"
                    onClick={() => {
                      save({ [entry.category]: entry.default_quantity }, {
                        onSuccess: () => setSaved(true),
                      })
                      handleReset(entry.category)
                    }}
                  >↺</button>
                )}
              </div>
            </div>
          )
        })}
      </div>

      <div className="settings__profile-actions">
        <button className="settings__save-btn" onClick={handleSave} disabled={isSaving || Object.keys(edits).length === 0}>
          {isSaving ? 'Guardando…' : 'Guardar porciones'}
        </button>
        {saved && <span className="settings__save-ok">Guardado</span>}
      </div>
    </div>
  )
}

// ── Panel principal ───────────────────────────────────────────────────────────

export type SettingsSubTab = 'goal' | 'profile' | 'portions'

const SUB_ICON_PROPS = { size: 15, strokeWidth: 1.5 }

export const SETTINGS_SUBTABS: { id: SettingsSubTab; label: string; icon: ReactNode }[] = [
  { id: 'goal',     label: 'Objetivo CO₂', icon: <Target          {...SUB_ICON_PROPS} /> },
  { id: 'profile',  label: 'Preferencias', icon: <User            {...SUB_ICON_PROPS} /> },
  { id: 'portions', label: 'Porciones',    icon: <UtensilsCrossed {...SUB_ICON_PROPS} /> },
]

interface SettingsPanelProps {
  tab: SettingsSubTab
}

export function SettingsPanel({ tab }: SettingsPanelProps) {
  return (
    <div className="settings">
      {tab === 'goal'     && <GoalPanel />}
      {tab === 'profile'  && <ProfilePanel />}
      {tab === 'portions' && <PortionsPanel />}
    </div>
  )
}
