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
  // interpolación entre niveles
  if (t < 4) return LEVELS[0]
  if (t < 6) return LEVELS[1]
  if (t < 8) return LEVELS[2]
  return LEVELS[3]
}

function getSliderBackground(value: number) {
  const pct = ((value - 2) / (8 - 2)) * 100
  return `linear-gradient(to right, #4ade80 0%, #a3e635 33%, #facc15 66%, #ef4444 100%)`
}

export function SettingsPanel() {
  const { settings, update } = useSettings()
  const t = settings.annualGoalTonnes
  const level = getLevelInfo(t)
  const monthlyKg = Math.round(t * 1000 / 12)
  const dailyKg = (t * 1000 / 365).toFixed(1)

  return (
    <div style={{ maxWidth: '560px', margin: '0 auto', padding: '8px 0' }}>
      <h2 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '8px' }}>Configuración</h2>
      <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '32px' }}>
        Personaliza tu objetivo de huella de carbono anual. Todos los indicadores de la aplicación se recalcularán según este valor.
      </p>

      {/* ── Slider section ─────────────────────────────────────────── */}
      <div style={{
        background: 'var(--surface-2)',
        border: '1px solid var(--border)',
        borderRadius: '14px',
        padding: '28px 24px',
        marginBottom: '24px',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '20px' }}>
          <div>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '0 0 4px' }}>META ANUAL</p>
            <p style={{ fontSize: '38px', fontWeight: 700, fontFamily: 'DM Mono', color: level.color, margin: 0, lineHeight: 1 }}>
              {t} t
              <span style={{ fontSize: '14px', color: 'var(--text-muted)', fontWeight: 400, marginLeft: '8px' }}>CO₂/año</span>
            </p>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>equivale a</div>
            <div style={{ fontSize: '14px', fontFamily: 'DM Mono' }}>
              <span style={{ color: level.color }}>{monthlyKg} kg</span>
              <span style={{ color: 'var(--text-muted)' }}>/mes · </span>
              <span style={{ color: level.color }}>{dailyKg} kg</span>
              <span style={{ color: 'var(--text-muted)' }}>/día</span>
            </div>
          </div>
        </div>

        {/* Slider */}
        <div style={{ position: 'relative', marginBottom: '12px' }}>
          <input
            type="range"
            min={2}
            max={8}
            step={1}
            value={t}
            onChange={e => update({ annualGoalTonnes: Number(e.target.value) })}
            style={{
              width: '100%',
              appearance: 'none',
              height: '8px',
              borderRadius: '4px',
              outline: 'none',
              cursor: 'pointer',
              background: getSliderBackground(t),
            }}
          />
        </div>

        {/* Tick labels */}
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)' }}>
          {[2, 3, 4, 5, 6, 7, 8].map(v => (
            <span key={v} style={{ color: v === t ? level.color : 'var(--text-muted)', fontWeight: v === t ? 600 : 400 }}>
              {v}t
            </span>
          ))}
        </div>

        {/* Level badges */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '16px' }}>
          {LEVELS.map(l => (
            <button
              key={l.t}
              onClick={() => update({ annualGoalTonnes: l.t })}
              style={{
                padding: '4px 10px',
                borderRadius: '20px',
                border: `1px solid ${t === l.t ? l.color : 'var(--border)'}`,
                background: t === l.t ? `${l.color}22` : 'transparent',
                color: t === l.t ? l.color : 'var(--text-muted)',
                fontSize: '11px',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              {l.t} t
            </button>
          ))}
        </div>
      </div>

      {/* ── Explanation card ───────────────────────────────────────── */}
      <div style={{
        background: 'var(--surface-2)',
        border: `1px solid ${level.color}44`,
        borderLeft: `4px solid ${level.color}`,
        borderRadius: '10px',
        padding: '20px 20px 20px 24px',
        marginBottom: '24px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
          <span style={{ fontSize: '20px', fontWeight: 700, color: level.color, fontFamily: 'DM Mono' }}>
            {level.label}
          </span>
          <span style={{
            padding: '2px 10px',
            borderRadius: '20px',
            background: `${level.tempColor}22`,
            color: level.tempColor,
            fontSize: '12px',
            fontWeight: 600,
          }}>
            🌡️ {level.temp}
          </span>
        </div>
        <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.7' }}>
          {level.desc}
        </p>
      </div>

      {/* ── Context info ───────────────────────────────────────────── */}
      <div style={{
        background: 'var(--surface-2)',
        border: '1px solid var(--border)',
        borderRadius: '10px',
        padding: '18px 20px',
        fontSize: '12px',
        color: 'var(--text-muted)',
        lineHeight: '1.7',
      }}>
        <p style={{ margin: '0 0 10px', fontWeight: 600, color: 'var(--text)', fontSize: '13px' }}>¿Qué es la huella de carbono?</p>
        <p style={{ margin: '0 0 8px' }}>
          La huella de carbono mide la cantidad de gases de efecto invernadero (CO₂ y equivalentes) que generamos con nuestras actividades diarias: lo que comemos, cómo nos desplazamos, la energía que consumimos o lo que compramos.
        </p>
        <p style={{ margin: 0 }}>
          Cuanto más alta sea tu meta anual, menor presión sentirás al principio — pero mayor será tu impacto en el clima. La ciencia indica que para limitar el calentamiento a <strong style={{ color: '#4ade80' }}>1,5 °C</strong> necesitamos reducir a <strong style={{ color: '#4ade80' }}>~2 t/persona/año</strong> antes de 2050. Empieza donde puedas y ve bajando poco a poco.
        </p>
      </div>
    </div>
  )
}
