import { useSettings } from '../hooks/useSettings'

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

export function SettingsPanel() {
  const { settings, update } = useSettings()
  const t = settings.annualGoalTonnes
  const level = getLevelInfo(t)
  const monthlyKg = Math.round(t * 1000 / 12)
  const dailyKg = (t * 1000 / 365).toFixed(1)

  return (
    <div className="settings">
      <h2 className="settings__title">Configuración</h2>
      <p className="settings__subtitle">
        Personaliza tu objetivo de huella de carbono anual. Todos los indicadores de la aplicación se recalcularán según este valor.
      </p>

      {/* ── Slider section ─────────────────────────────────────────── */}
      <div className="settings__card">
        <div className="settings__card-header">
          <div>
            <p className="settings__goal-label">META ANUAL</p>
            <p className="settings__goal-value" style={{ color: level.color }}>
              {t} t
              <span className="settings__goal-unit">CO₂/año</span>
            </p>
          </div>
          <div className="settings__goal-equiv">
            <div className="settings__equiv-label">equivale a</div>
            <div className="settings__equiv-values">
              <span style={{ color: level.color }}>{monthlyKg} kg</span>
              <span style={{ color: 'var(--text-muted)' }}>/mes · </span>
              <span style={{ color: level.color }}>{dailyKg} kg</span>
              <span style={{ color: 'var(--text-muted)' }}>/día</span>
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
            <span key={v} style={{ color: v === t ? level.color : 'var(--text-muted)', fontWeight: v === t ? 600 : 400 }}>
              {v}t
            </span>
          ))}
        </div>

        <div className="settings__level-btns">
          {LEVELS.map(l => (
            <button
              key={l.t}
              onClick={() => update({ annualGoalTonnes: l.t })}
              className="settings__level-btn"
              style={{
                border: `1px solid ${t === l.t ? l.color : 'var(--border)'}`,
                background: t === l.t ? `${l.color}22` : 'transparent',
                color: t === l.t ? l.color : 'var(--text-muted)',
              }}
            >
              {l.t} t
            </button>
          ))}
        </div>
      </div>

      {/* ── Explanation card ───────────────────────────────────────── */}
      <div
        className="settings__info-card"
        style={{
          border: `1px solid ${level.color}44`,
          borderLeft: `4px solid ${level.color}`,
        }}
      >
        <div className="settings__info-header">
          <span className="settings__info-name" style={{ color: level.color }}>
            {level.label}
          </span>
          <span
            className="settings__temp-badge"
            style={{ background: `${level.tempColor}22`, color: level.tempColor }}
          >
            🌡️ {level.temp}
          </span>
        </div>
        <p className="settings__info-desc">{level.desc}</p>
      </div>

      {/* ── Context info ───────────────────────────────────────────── */}
      <div className="settings__context-box">
        <p className="settings__context-title">¿Qué es la huella de carbono?</p>
        <p className="settings__context-desc">
          La huella de carbono mide la cantidad de gases de efecto invernadero (CO₂ y equivalentes) que generamos con nuestras actividades diarias: lo que comemos, cómo nos desplazamos, la energía que consumimos o lo que compramos.
        </p>
        <p className="settings__context-desc">
          Cuanto más alta sea tu meta anual, menor presión sentirás al principio — pero mayor será tu impacto en el clima. La ciencia indica que para limitar el calentamiento a <strong style={{ color: '#4ade80' }}>1,5 °C</strong> necesitamos reducir a <strong style={{ color: '#4ade80' }}>~2 t/persona/año</strong> antes de 2050. Empieza donde puedas y ve bajando poco a poco.
        </p>
      </div>
    </div>
  )
}
