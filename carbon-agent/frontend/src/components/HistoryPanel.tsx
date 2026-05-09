import { useState } from 'react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { useHistory, useDeleteHistory, useDeleteActivity } from '../hooks/useCarbon'

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
  const deleteHistory = useDeleteHistory(userId)
  const deleteActivity = useDeleteActivity(userId)
  const [confirmClear, setConfirmClear] = useState(false)

  if (isLoading) return <div className="panel-state">Cargando historial…</div>
  if (isError) return <div className="panel-state panel-state--error">Error al cargar el historial.</div>

  if (!activities?.length) return (
    <div className="panel-state">
      <span className="panel-state__icon">📋</span>
      <p>Aún no hay actividades registradas.</p>
      <p className="panel-state__hint">Escribe tu primera actividad en el chat.</p>
    </div>
  )

  const handleClearAll = () => {
    if (!confirmClear) { setConfirmClear(true); return }
    deleteHistory.mutate()
    setConfirmClear(false)
  }

  return (
    <div className="history-panel">
      {/* Header con botón borrar todo */}
      <div className="history-header">
        <span className="history-header__count">{activities.length} actividad{activities.length !== 1 ? 'es' : ''}</span>
        <button
          className={`btn-clear ${confirmClear ? 'btn-clear--confirm' : ''}`}
          onClick={handleClearAll}
          onBlur={() => setConfirmClear(false)}
          disabled={deleteHistory.isPending}
        >
          {deleteHistory.isPending ? 'Borrando…' : confirmClear ? '¿Seguro? Pulsa de nuevo' : '🗑 Borrar todo'}
        </button>
      </div>

      <ul className="history-list">
        {activities.map((activity) => {
          const total = activity.emissions.reduce((s, e) => s + e.amount_kg_co2e, 0)
          return (
            <li key={activity.id} className="history-item">
              <div className="history-item__top">
                <p className="history-item__text">{activity.raw_text}</p>
                <div className="history-item__right">
                  <span className="history-item__total" style={{ color: co2Color(total) }}>
                    {total > 0 ? `${total.toFixed(3)} kg` : '—'}
                  </span>
                  <button
                    className="btn-delete-item"
                    onClick={() => deleteActivity.mutate(activity.id)}
                    disabled={deleteActivity.isPending}
                    title="Eliminar esta actividad"
                    aria-label="Eliminar actividad"
                  >
                    ✕
                  </button>
                </div>
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