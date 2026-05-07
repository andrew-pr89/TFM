import type { ChatMessage } from '../types'

interface Props {
  message: ChatMessage
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
        <p>{text}</p>
      </div>
    )
  }

  if (role === 'error') {
    return (
      <div className="bubble bubble--error">
        <span className="bubble__icon">⚠</span>
        <p>{text}</p>
      </div>
    )
  }

  // assistant
  const total = data?.total_kg_co2e ?? 0
  const emissions = data?.activity.emissions ?? []
  const recommendation = data?.recommendation ?? text

  return (
    <div className="bubble bubble--assistant">
      {/* Total badge */}
      {data && (
        <div className="emission-badge" style={{ '--badge-color': co2Color(total) } as React.CSSProperties}>
          <span className="emission-badge__value">{co2Label(total)}</span>
          <span className="emission-badge__label">CO₂e</span>
        </div>
      )}

      {/* Recommendation */}
      <p className="recommendation">{recommendation}</p>
    </div>
  )
}
