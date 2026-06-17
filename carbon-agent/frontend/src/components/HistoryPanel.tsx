import { useState, useMemo, useRef } from 'react'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { Trash2, Pencil, ChevronUp, ChevronDown } from 'lucide-react'
import { useHistory, useDeleteHistory, useDeleteActivity, useEditActivity } from '../hooks/useCarbon'
import type { ActivityOut } from '../types'
import type { CSSProperties } from 'react'

type SortCol = 'date' | 'description' | 'category' | 'quantity' | 'co2'
type SortDir = 'asc' | 'desc'

interface FlatRow {
  key:         string
  activityId:  number
  emissionId:  number | null
  date:        Date
  description: string
  category:    string
  quantity:    string
  quantityNum: number
  co2:         number | null
  activity:    ActivityOut
}

function co2BadgeVars(kg: number): { '--badge-color': string; '--badge-text-color': string } {
  if (kg === 0) return { '--badge-color': 'var(--c-neutral)', '--badge-text-color': 'var(--c-neutral-text)' }
  if (kg < 1)   return { '--badge-color': 'var(--c-low)',     '--badge-text-color': 'var(--c-low-text)'     }
  if (kg < 5)   return { '--badge-color': 'var(--c-mid)',     '--badge-text-color': 'var(--c-mid-text)'     }
  return           { '--badge-color': 'var(--c-high)',    '--badge-text-color': 'var(--c-high-text)'    }
}

function SortArrows({ col, active, dir }: { col: SortCol; active: SortCol; dir: SortDir }) {
  const isActive = col === active
  return (
    <span className="sort-arrows">
      <ChevronUp  size={10} className={`sort-arrows__up   ${isActive && dir === 'asc'  ? 'sort-arrows--on' : ''}`} />
      <ChevronDown size={10} className={`sort-arrows__down ${isActive && dir === 'desc' ? 'sort-arrows--on' : ''}`} />
    </span>
  )
}

export function HistoryPanel() {
  const { data: activities, isLoading, isError } = useHistory()
  const deleteHistory  = useDeleteHistory()
  const deleteActivity = useDeleteActivity()
  const editActivity   = useEditActivity()

  const [confirmClear,      setConfirmClear]      = useState(false)
  const [editingId,         setEditingId]         = useState<number | null>(null)
  const [editingEmissionId, setEditingEmissionId] = useState<number | null>(null)
  const [editText, setEditText] = useState('')
  const [editDate, setEditDate] = useState('')

  const [filterText, setFilterText] = useState('')
  const [filterDate, setFilterDate] = useState('')
  const [sortCol,    setSortCol]    = useState<SortCol>('date')
  const [sortDir,    setSortDir]    = useState<SortDir>('desc')
  const tableWrapRef = useRef<HTMLDivElement>(null)

  const startEdit = (activity: ActivityOut, emissionId?: number) => {
    setEditingId(activity.id)
    setEditingEmissionId(emissionId ?? activity.emissions[0]?.id ?? null)
    setEditText(activity.raw_text)
    setEditDate(new Date(activity.created_at).toISOString().slice(0, 16))
  }
  const cancelEdit = () => { setEditingId(null); setEditingEmissionId(null) }
  const saveEdit = (id: number) => {
    editActivity.mutate(
      { id, rawText: editText, createdAt: editDate ? new Date(editDate).toISOString() : null },
      { onSuccess: () => { setEditingId(null); setEditingEmissionId(null) } },
    )
  }

  const handleSort = (col: SortCol) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortCol(col); setSortDir('asc') }
  }

  const handleClearAll = () => {
    if (!confirmClear) { setConfirmClear(true); return }
    deleteHistory.mutate()
    setConfirmClear(false)
  }

  const rows = useMemo<FlatRow[]>(() => {
    if (!activities) return []
    const flat: FlatRow[] = []
    for (const activity of activities) {
      const date = new Date(activity.created_at)
      if (activity.emissions.length === 0) {
        flat.push({
          key: `a-${activity.id}`,
          activityId: activity.id,
          emissionId: null,
          date,
          description: activity.raw_text,
          category: '',
          quantity: '',
          quantityNum: 0,
          co2: null,
          activity,
        })
      } else {
        for (const em of activity.emissions) {
          flat.push({
            key: `e-${em.id}`,
            activityId: activity.id,
            emissionId: em.id,
            date,
            description: em.description || em.factor.display_name,
            category: em.factor.main_category,
            quantity: `${em.quantity} ${em.factor.unit}`,
            quantityNum: em.quantity,
            co2: em.amount_kg_co2e,
            activity,
          })
        }
      }
    }
    return flat
  }, [activities])

  const filtered = useMemo(() => {
    let r = rows
    if (filterText.trim()) {
      const q = filterText.toLowerCase()
      r = r.filter(row =>
        row.description.toLowerCase().includes(q) ||
        row.category.toLowerCase().includes(q)
      )
    }
    if (filterDate) {
      r = r.filter(row => format(row.date, 'yyyy-MM-dd') === filterDate)
    }
    return [...r].sort((a, b) => {
      let cmp = 0
      switch (sortCol) {
        case 'date':        cmp = a.date.getTime() - b.date.getTime(); break
        case 'description': cmp = a.description.localeCompare(b.description); break
        case 'category':    cmp = a.category.localeCompare(b.category); break
        case 'quantity':    cmp = a.quantityNum - b.quantityNum; break
        case 'co2':         cmp = (a.co2 ?? -1) - (b.co2 ?? -1); break
      }
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [rows, filterText, filterDate, sortCol, sortDir])

  if (isLoading) return <div className="panel-state">Cargando historial…</div>
  if (isError)   return <div className="panel-state panel-state--error">Error al cargar el historial.</div>
  if (!activities?.length) return (
    <div className="panel-state">
      <span className="panel-state__icon">📋</span>
      <p>Aún no hay actividades registradas.</p>
      <p className="panel-state__hint">Escribe tu primera actividad en el chat.</p>
    </div>
  )

  return (
    <div className="history-panel">
      <div className="history-header">
        <div className="history-filters">
          <input
            className="history-filter__input"
            type="search"
            placeholder="Buscar actividad…"
            value={filterText}
            onChange={e => setFilterText(e.target.value)}
          />
          <input
            className="history-filter__date"
            type="date"
            value={filterDate}
            onChange={e => setFilterDate(e.target.value)}
          />
          {(filterText || filterDate) && (
            <button className="history-filter__clear" onClick={() => { setFilterText(''); setFilterDate('') }}>
              Limpiar
            </button>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className="history-header__count">{filtered.length} resultado{filtered.length !== 1 ? 's' : ''}</span>
          <button
            className={`btn-clear ${confirmClear ? 'btn-clear--confirm' : ''}`}
            onClick={handleClearAll}
            onBlur={() => setConfirmClear(false)}
            disabled={deleteHistory.isPending}
          >
            {deleteHistory.isPending ? 'Borrando…' : confirmClear ? '¿Seguro? Pulsa de nuevo' : 'Borrar todo'}
          </button>
        </div>
      </div>

      <div className="admin-table-wrap" ref={tableWrapRef}>
        <table className="admin-table">
          <thead>
            <tr>
              {([
                ['date',        'Fecha'],
                ['description', 'Actividad'],
                ['category',    'Categoría'],
                ['quantity',    'Cantidad'],
                ['co2',         'CO₂e'],
              ] as [SortCol, string][]).map(([col, label]) => (
                <th key={col} className="history-th--sortable" onClick={() => handleSort(col)}>
                  <span className="history-th__inner">
                    {sortCol === col && <span className="sort-dot" />}
                    {label}
                    <SortArrows col={col} active={sortCol} dir={sortDir} />
                  </span>
                </th>
              ))}
              <th />
            </tr>
          </thead>
          <tbody>
            {filtered.map(row => {
              const isEditing = editingId === row.activityId && editingEmissionId === row.emissionId
              return (
                <tr key={row.key} className="admin-table__row">
                  {isEditing ? (
                    <td colSpan={6}>
                      <div className="history-item__edit-form">
                        <input type="datetime-local" className="history-edit__date" value={editDate} onChange={e => setEditDate(e.target.value)} />
                        <textarea className="history-edit__text" value={editText} rows={2} onChange={e => setEditText(e.target.value)} />
                        <div className="history-edit__actions">
                          <button className="btn-save-edit" disabled={editActivity.isPending} onClick={() => saveEdit(row.activityId)}>
                            {editActivity.isPending ? 'Guardando…' : 'Guardar'}
                          </button>
                          <button className="btn-cancel-edit" onClick={cancelEdit}>Cancelar</button>
                        </div>
                      </div>
                    </td>
                  ) : (
                    <>
                      <td className="admin-table__date">{format(row.date, "dd/MM/yyyy")}</td>
                      <td className="admin-table__term">{row.description}</td>
                      <td className="admin-table__cat">{row.category || <span className="admin-table__placeholder">—</span>}</td>
                      <td className="admin-table__num">{row.quantity || <span className="admin-table__placeholder">—</span>}</td>
                      <td>
                        {row.co2 !== null
                          ? <span className="co2-badge" style={co2BadgeVars(row.co2) as CSSProperties}>{row.co2.toFixed(3)} kg</span>
                          : <span className="admin-table__placeholder">—</span>
                        }
                      </td>
                      <td>
                        <div className="history-item__right">
                          <button className="btn-edit-item" onClick={() => startEdit(row.activity, row.emissionId ?? undefined)} title="Editar"><Pencil size={17} /></button>
                          <button className="btn-delete-item" onClick={() => deleteActivity.mutate(row.activityId)} disabled={deleteActivity.isPending} title="Eliminar"><Trash2 size={17} /></button>
                        </div>
                      </td>
                    </>
                  )}
                </tr>
              )
            })}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)' }}>
                  Sin resultados para esta búsqueda.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
