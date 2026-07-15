import { AlertCircle } from 'lucide-react'
import type { ChatMessage } from '../types'

interface Props {
  message: ChatMessage
}

// Longitud máxima que se muestra en la burbuja del usuario; el resto se
// recorta con puntos suspensivos (el texto completo se conserva en el title).
const MAX_DISPLAY_CHARS = 100

function truncate(text: string): string {
  return text.length > MAX_DISPLAY_CHARS
    ? `${text.slice(0, MAX_DISPLAY_CHARS)}…`
    : text
}

function qtyLabel(qty: number, unit: string): string {
  if (unit === 'kg')    return qty < 1 ? `${Math.round(qty * 1000)} g` : `${qty} kg`
  if (unit === 'litro') return qty < 1 ? `${Math.round(qty * 1000)} ml` : `${qty.toFixed(2)} l`
  if (unit === 'kWh')   return `${qty} kWh`
  if (unit === 'hora')  return qty === 1 ? '1 h' : `${qty} h`
  if (unit === 'km')    return `${qty} km`
  return `${qty} ${unit}`
}

function qtyPrefix(unit: string): string {
  if (unit === 'km')   return 'distancia'
  if (unit === 'hora') return 'tiempo'
  return 'ración'
}

function co2Color(kg: number): string {
  if (kg === 0) return 'var(--c-neutral)'
  if (kg < 1) return 'var(--c-low)'
  if (kg < 5) return 'var(--c-mid)'
  return 'var(--c-high)'
}

function co2Label(kg: number): string {
  if (kg === 0) return '—'
  if (kg < 0.001) return `${(kg * 1000).toFixed(1)} g`
  return `${kg.toFixed(3)} kg`
}

export function ChatBubble({ message }: Props) {
  const { role, text, data } = message

  if (role === 'user') {
    return (
      <div className="bubble bubble--user">
        <p title={text.length > MAX_DISPLAY_CHARS ? text : undefined}>{truncate(text)}</p>
      </div>
    )
  }

  if (role === 'error') {
    return (
      <div className="bubble bubble--error">
        <AlertCircle size={16} className="icon" />
        <p>{text}</p>
      </div>
    )
  }

  // assistant — sin datos (pregunta aclaratoria o mensaje informativo)
  if (!data || data.total_kg_co2e === 0) {
    const isQ = Boolean(data?.is_question)
    return (
      <div className={`bubble bubble--assistant ${isQ ? 'bubble--question' : ''}`}>
        <p>{isQ && <AlertCircle size={15} className="icon bubble__question-icon" />}{text}</p>
        {isQ && <p className="bubble__question-hint">Responde con la cantidad para calcular la huella</p>}
      </div>
    )
  }

  // assistant — con datos de emisiones
  const total = data.total_kg_co2e
  const emissions = data.activity.emissions
  const clarifyingQ = data.clarifying_question

  return (
    <div className="bubble bubble--assistant">
      {/* Total badge */}
      <div className="emission-badge" style={{ '--badge-color': co2Color(total) } as React.CSSProperties}>
        <span>{co2Label(total)}</span>
        <span>CO₂e</span>
      </div>

      {/* Breakdown */}
      {emissions.length > 0 && (
        <ul className="emission-list">
          {emissions.map((e) => (
            <li key={e.id} className="emission-item">
              <span>
                {(e.description || e.factor.display_name).replace(/\s*\(ración estándar\)/i, '').trim()}
                <small>{qtyPrefix(e.factor.unit)} {qtyLabel(e.quantity, e.factor.unit)}</small>
              </span>
              <span className="emission-item__bar-wrap">
                <span
                  className="emission-item__bar"
                  style={{
                    width: `${Math.min((e.amount_kg_co2e / Math.max(total, 0.001)) * 100, 100)}%`,
                    '--bar-color': co2Color(e.amount_kg_co2e),
                  } as React.CSSProperties}
                />
              </span>
              <span>{co2Label(e.amount_kg_co2e)} <small>CO₂e</small></span>
            </li>
          ))}
        </ul>
      )}

      {/* Pregunta pendiente cuando hay emisiones + actividad incompleta */}
      {clarifyingQ && (
        <div className="bubble__pending-question">
          <p><span className="bubble__question-icon">💬 </span>{clarifyingQ}</p>
          <p className="bubble__question-hint">Responde para completar el cálculo</p>
        </div>
      )}

    </div>
  )
}