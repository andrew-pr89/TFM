import { useState } from 'react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { useHistory, useDeleteHistory, useDeleteActivity, useEditActivity } from '../hooks/useCarbon'
import type { ActivityOut } from '../types'

interface Props {
  userId?: string
}

const TrashIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" width="13" height="13">
    <path fillRule="evenodd" d="M8.75 1A2.75 2.75 0 0 0 6 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 1 0 .23 1.482l.149-.022.841 10.518A2.75 2.75 0 0 0 7.596 19h4.807a2.75 2.75 0 0 0 2.742-2.53l.841-10.52.149.023a.75.75 0 0 0 .23-1.482A41.03 41.03 0 0 0 14 4.193V3.75A2.75 2.75 0 0 0 11.25 1h-2.5ZM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4ZM8.58 7.72a.75.75 0 0 0-1.5.06l.3 7.5a.75.75 0 1 0 1.5-.06l-.3-7.5Zm4.34.06a.75.75 0 1 0-1.5-.06l-.3 7.5a.75.75 0 1 0 1.5.06l.3-7.5Z" clipRule="evenodd" />
  </svg>
)

const PencilIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" width="13" height="13">
    <path d="m5.433 13.917 1.262-3.155A4 4 0 0 1 7.58 9.42l6.92-6.918a2.121 2.121 0 0 1 3 3l-6.92 6.918c-.383.383-.84.685-1.343.886l-3.154 1.262a.5.5 0 0 1-.65-.65Z" />
    <path d="M3.5 5.75c0-.69.56-1.25 1.25-1.25H10A.75.75 0 0 0 10 3H4.75A2.75 2.75 0 0 0 2 5.75v9.5A2.75 2.75 0 0 0 4.75 18h9.5A2.75 2.75 0 0 0 17 15.25V10a.75.75 0 0 0-1.5 0v5.25c0 .69-.56 1.25-1.25 1.25h-9.5c-.69 0-1.25-.56-1.25-1.25v-9.5Z" />
  </svg>
)

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
  const editActivity = useEditActivity(userId)
  const [confirmClear, setConfirmClear] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editText, setEditText] = useState('')
  const [editDate, setEditDate] = useState('')

  const startEdit = (activity: ActivityOut) => {
    setEditingId(activity.id)
    setEditText(activity.raw_text)
    setEditDate(new Date(activity.created_at).toISOString().slice(0, 16))
  }

  const cancelEdit = () => setEditingId(null)

  const saveEdit = (id: number) => {
    editActivity.mutate(
      { id, rawText: editText, createdAt: editDate ? new Date(editDate).toISOString() : null },
      { onSuccess: () => setEditingId(null) },
    )
  }

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
          const isEditing = editingId === activity.id

          return (
            <li key={activity.id} className="history-item">
              {isEditing ? (
                <div className="history-item__edit-form">
                  <input
                    type="datetime-local"
                    className="history-edit__date"
                    value={editDate}
                    onChange={(e) => setEditDate(e.target.value)}
                  />
                  <textarea
                    className="history-edit__text"
                    value={editText}
                    rows={2}
                    onChange={(e) => setEditText(e.target.value)}
                  />
                  <div className="history-edit__actions">
                    <button
                      className="btn-save-edit"
                      disabled={editActivity.isPending}
                      onClick={() => saveEdit(activity.id)}
                    >
                      {editActivity.isPending ? 'Guardando…' : 'Guardar'}
                    </button>
                    <button className="btn-cancel-edit" onClick={cancelEdit}>
                      Cancelar
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="history-item__top">
                    <div className="history-item__text">
                      {activity.emissions.length === 0 ? (
                        // Sin emisiones: mostrar texto del usuario
                        <span>{activity.raw_text}</span>
                      ) : activity.emissions.length === 1 ? (
                        // Una emisión: mostrar la descripción procesada
                        <span>{activity.emissions[0].description || activity.emissions[0].factor.display_name}</span>
                      ) : (
                        // Varias emisiones: listar descripciones
                        <ul className="history-item__desc-list">
                          {activity.emissions.map((e) => (
                            <li key={e.id}>{e.description || e.factor.display_name}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <div className="history-item__right">
                      <span className="history-item__total" style={{ color: co2Color(total) }}>
                        {total > 0 ? `${total.toFixed(3)} kg` : '—'}
                      </span>
                      <button
                        className="btn-edit-item"
                        onClick={() => startEdit(activity)}
                        title="Editar actividad"
                        aria-label="Editar actividad"
                      >
                        <PencilIcon />
                      </button>
                      <button
                        className="btn-delete-item"
                        onClick={() => deleteActivity.mutate(activity.id)}
                        disabled={deleteActivity.isPending}
                        title="Eliminar esta actividad"
                        aria-label="Eliminar actividad"
                      >
                        <TrashIcon />
                      </button>
                    </div>
                  </div>
                  <div className="history-item__meta">
                    {activity.emissions.length > 0 && (
                      <span style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>
                        {activity.emissions.map(e => `${e.quantity} ${e.factor.unit}`).join(' · ')}
                      </span>
                    )}
                    <time>{format(new Date(activity.created_at), "d MMM, HH:mm", { locale: es })}</time>
                  </div>
                </>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
