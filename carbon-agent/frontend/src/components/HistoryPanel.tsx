import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { useHistory } from '../hooks/useCarbon'

interface Props {
  userId?: string
}

function co2Color(kg: number) {
  if (kg === 0) return 'var(--c-neutral)'
  if (kg < 1) return 'var(--c-low)'
  if (kg < 5) return 'var(--c-mid)'
  return 'var(--c-high)'
}

export function HistoryPanel({ userId = 'default' }: Props) {
  const { data: activities, isLoading, isError } = useHistory(userId)

  if (isLoading) return <div className="panel-state">Cargando historial…</div>
  if (isError) return <div className="panel-state panel-state--error">Error al cargar el historial.</div>
  if (!activities?.length) return (
    <div className="panel-state">
      <span className="panel-state__icon">📋</span>
      <p>Aún no hay actividades registradas.</p>
      <p className="panel-state__hint">Escribe tu primera actividad en el chat.</p>
    </div>
  )

  return (
    <div className="history-panel">
      <ul className="history-list">
        {activities.map((activity) => {
          const total = activity.emissions.reduce((s, e) => s + e.amount_kg_co2e, 0)
          return (
            <li key={activity.id} className="history-item">
              <div className="history-item__top">
                <p className="history-item__text">{activity.raw_text}</p>
                <span
                  className="history-item__total"
                  style={{ color: co2Color(total) }}
                >
                  {total > 0 ? `${total.toFixed(3)} kg` : '—'}
                </span>
              </div>
              <div className="history-item__meta">
                <time>{format(new Date(activity.created_at), "d MMM, HH:mm", { locale: es })}</time>
                {activity.emissions.length > 0 && (
                  <span>{activity.emissions.length} actividad{activity.emissions.length > 1 ? 'es' : ''}</span>
                )}
              </div>
              {activity.emissions.length > 0 && (
                <ul className="history-item__emissions">
                  {activity.emissions.map((e) => (
                    <li key={e.id}>
                      <span>{e.factor.display_name}</span>
                      <span style={{ color: co2Color(e.amount_kg_co2e) }}>{e.amount_kg_co2e.toFixed(3)} kg</span>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
