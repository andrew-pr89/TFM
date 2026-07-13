import { useState, useMemo, useRef } from 'react'

function formatQty(qty: number, unit: string): string {
  if (unit === 'kg')    return qty < 1 ? `${Math.round(qty * 1000)} g` : `${qty} kg`
  if (unit === 'litro') return qty < 1 ? `${Math.round(qty * 1000)} ml` : `${qty.toFixed(2)} l`
  if (unit === 'kWh')   return `${qty} kWh`
  if (unit === 'hora')  return qty === 1 ? '1 h' : `${qty} h`
  if (unit === 'km')    return `${qty} km`
  return `${qty} ${unit}`
}

function toDisplayUnit(qty: number, unit: string): { value: number; displayUnit: string } {
  if (unit === 'kg'    && qty < 1) return { value: Math.round(qty * 1000), displayUnit: 'g' }
  if (unit === 'litro' && qty < 1) return { value: Math.round(qty * 1000), displayUnit: 'ml' }
  return { value: qty, displayUnit: unit }
}

function toBaseUnit(value: number, displayUnit: string): number {
  if (displayUnit === 'g')  return value / 1000
  if (displayUnit === 'ml') return value / 1000
  return value
}
import { format } from 'date-fns'
import {
  Trash2, Pencil, ChevronUp, ChevronDown, X, CalendarDays, MoreVertical, Search, Tag, RefreshCw,
  Utensils, Car, Zap, Recycle, ShoppingBag, Music, Leaf, type LucideIcon,
} from 'lucide-react'
import { useHistory, useDeleteActivity, useEditActivity, useEditEmissionQuantity } from '../hooks/useCarbon'
import type { ActivityOut } from '../types'
import type { CSSProperties } from 'react'

const CATEGORY_COLORS: Record<string, string> = {
  Alimentación: 'var(--cat-alimentacion)',
  Transporte:   'var(--cat-transporte)',
  Energía:      'var(--cat-energia)',
  Residuos:     'var(--cat-residuos)',
  Compras:      'var(--cat-compras)',
  Ocio:         'var(--cat-ocio)',
}

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  Alimentación: Utensils,
  Transporte:   Car,
  Energía:      Zap,
  Residuos:     Recycle,
  Compras:      ShoppingBag,
  Ocio:         Music,
}

function categoryBadgeVars(category: string): { '--badge-color': string } {
  return { '--badge-color': CATEGORY_COLORS[category] ?? 'var(--c-neutral)' }
}

function CategoryIconBadge({ category }: { category: string }) {
  const Icon = CATEGORY_ICONS[category] ?? Leaf
  const color = CATEGORY_COLORS[category] ?? 'var(--c-neutral)'
  return (
    <span className="cat-icon-badge" style={{ '--cat-icon-color': color } as CSSProperties}>
      <Icon className="icon" />
    </span>
  )
}

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
      <ChevronUp   size={10} className={`icon${isActive && dir === 'asc'  ? ' sort-arrows--on' : ''}`} />
      <ChevronDown size={10} className={`icon${isActive && dir === 'desc' ? ' sort-arrows--on' : ''}`} />
    </span>
  )
}

export function HistoryPanel() {
  const { data: activities, isLoading, isError } = useHistory()
  const deleteActivity      = useDeleteActivity()
  const editActivity        = useEditActivity()
  const editEmissionQty     = useEditEmissionQuantity()

  const [editingId,         setEditingId]         = useState<number | null>(null)
  const [editingEmissionId, setEditingEmissionId] = useState<number | null>(null)
  const [editText,          setEditText]          = useState('')
  const [editDate,          setEditDate]          = useState('')
  const [editQuantity,      setEditQuantity]      = useState<string>('')
  const [editUnit,          setEditUnit]          = useState<string>('')

  const [openMenuKey, setOpenMenuKey] = useState<string | null>(null)
  const [expandedKey, setExpandedKey] = useState<string | null>(null)

  const [filterText,     setFilterText]     = useState('')
  const [filterDate,     setFilterDate]     = useState('')
  const [filterCategory, setFilterCategory] = useState('')
  const [categoryMenuOpen, setCategoryMenuOpen] = useState(false)
  const [sortCol,        setSortCol]        = useState<SortCol>('date')
  const [sortDir,        setSortDir]        = useState<SortDir>('desc')
  const tableWrapRef = useRef<HTMLDivElement>(null)
  const dateInputRef = useRef<HTMLInputElement & { showPicker?: () => void }>(null)

  const openDatePicker = () => {
    const el = dateInputRef.current
    if (!el) return
    if (el.showPicker) el.showPicker()
    else el.click()
  }

  const startEdit = (activity: ActivityOut, emissionId?: number, description?: string) => {
    setEditingId(activity.id)
    const emission = emissionId ? activity.emissions.find(e => e.id === emissionId) : activity.emissions[0]
    setEditingEmissionId(emissionId ?? emission?.id ?? null)
    setEditText(description ?? activity.raw_text)
    setEditDate(new Date(activity.created_at).toISOString().slice(0, 10))
    if (emission) {
      const { value, displayUnit } = toDisplayUnit(emission.quantity, emission.factor.unit)
      setEditQuantity(String(value))
      setEditUnit(displayUnit)
    } else {
      setEditQuantity('')
      setEditUnit('')
    }
  }
  const cancelEdit = () => { setEditingId(null); setEditingEmissionId(null) }
  const saveEdit = (id: number) => {
    const qty = parseFloat(editQuantity)
    if (editingEmissionId && !isNaN(qty) && qty > 0) {
      editEmissionQty.mutate(
        { emissionId: editingEmissionId, quantity: toBaseUnit(qty, editUnit) },
        { onSuccess: () => { setEditingId(null); setEditingEmissionId(null) } },
      )
    } else {
      editActivity.mutate(
        { id, rawText: editText, createdAt: editDate ? new Date(editDate).toISOString() : null },
        { onSuccess: () => { setEditingId(null); setEditingEmissionId(null) } },
      )
    }
  }

  const handleSort = (col: SortCol) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortCol(col); setSortDir('asc') }
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
            description: (em.description || em.factor.display_name).replace(/\s*\(ración estándar\)/i, '').trim(),
            category: em.factor.main_category,
            quantity: formatQty(em.quantity, em.factor.unit),
            quantityNum: em.quantity,
            co2: em.amount_kg_co2e,
            activity,
          })
        }
      }
    }
    return flat
  }, [activities])

  const categories = useMemo(() =>
    Array.from(new Set(rows.map(r => r.category).filter(Boolean))).sort()
  , [rows])

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
    if (filterCategory) {
      r = r.filter(row => row.category === filterCategory)
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
  }, [rows, filterText, filterDate, filterCategory, sortCol, sortDir])

  if (isLoading) return <div className="panel-state">Cargando historial…</div>
  if (isError)   return <div className="panel-state panel-state--error">Error al cargar el historial.</div>
  if (!activities?.length) return (
    <div className="panel-state">
      <p>Aún no hay actividades registradas.</p>
      <p className="panel-state__hint">Escribe tu primera actividad en el chat.</p>
    </div>
  )

  const FilterCategoryIcon = filterCategory ? (CATEGORY_ICONS[filterCategory] ?? Tag) : null

  return (
    <div className="history-panel">
      <div className="history-header">
        <div className="history-search">
          <Search size={16} className="icon history-search__icon" />
          <input
            className="history-search__input"
            type="search"
            placeholder="Buscar actividad…"
            value={filterText}
            onChange={e => setFilterText(e.target.value)}
          />
        </div>

        <div className="history-filter-row">
          <div className="history-filter-trigger">
            <button className="filter-chip-btn" onClick={openDatePicker}>
              <CalendarDays size={14} className="icon" /> Fecha <ChevronDown size={14} className="icon" />
            </button>
            <input
              ref={dateInputRef}
              type="date"
              className="history-filter-trigger__hidden-input"
              value={filterDate}
              onChange={e => setFilterDate(e.target.value)}
            />
          </div>

          <div className="history-filter-trigger">
            <button className="filter-chip-btn" onClick={() => setCategoryMenuOpen(v => !v)}>
              <Tag size={14} className="icon" /> Categoría <ChevronDown size={14} className="icon" />
            </button>
            {categoryMenuOpen && (
              <>
                <div className="history-card__menu-overlay" onClick={() => setCategoryMenuOpen(false)} />
                <div className="history-card__menu-popover history-filter-popover">
                  <button
                    className="history-card__menu-item"
                    onClick={() => { setFilterCategory(''); setCategoryMenuOpen(false) }}
                  >
                    Todas las categorías
                  </button>
                  {categories.map(cat => (
                    <button
                      key={cat}
                      className="history-card__menu-item"
                      onClick={() => { setFilterCategory(cat); setCategoryMenuOpen(false) }}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>

          {(filterText || filterDate || filterCategory) && (
            <button
              className="history-filter-clear"
              onClick={() => { setFilterText(''); setFilterDate(''); setFilterCategory('') }}
            >
              <RefreshCw size={13} className="icon" /> Limpiar
            </button>
          )}
        </div>

        {(filterDate || filterCategory) && (
          <div className="history-filter-tags">
            {filterDate && (
              <span className="history-filter-tag">
                <CalendarDays size={13} className="icon" />
                {format(new Date(filterDate + 'T00:00:00'), 'dd/MM/yyyy')}
                <button onClick={() => setFilterDate('')} title="Quitar filtro de fecha">
                  <X size={13} className="icon" />
                </button>
              </span>
            )}
            {filterCategory && FilterCategoryIcon && (
              <span className="history-filter-tag">
                <FilterCategoryIcon size={13} className="icon" />
                {filterCategory}
                <button onClick={() => setFilterCategory('')} title="Quitar filtro de categoría">
                  <X size={13} className="icon" />
                </button>
              </span>
            )}
          </div>
        )}

        <span className="history-header__count">Mostrando {filtered.length} de {rows.length} actividades</span>
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
                  <span>
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
                        <input type="date" className="history-edit__date" value={editDate} onChange={e => setEditDate(e.target.value)} />
                        <p className="history-edit__text-readonly">{editText}</p>
                        {editUnit && (
                          <div className="history-edit__qty-row">
                            <input
                              type="number"
                              min="0"
                              step="any"
                              className="history-edit__qty"
                              value={editQuantity}
                              onChange={e => setEditQuantity(e.target.value)}
                            />
                            <span className="history-edit__unit">{editUnit}</span>
                          </div>
                        )}
                        <div className="history-edit__actions">
                          <button disabled={editActivity.isPending} onClick={() => saveEdit(row.activityId)}>
                            {editActivity.isPending ? 'Guardando…' : 'Guardar'}
                          </button>
                          <button className="btn-light" onClick={cancelEdit}>Cancelar</button>
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
                          <button onClick={() => startEdit(row.activity, row.emissionId ?? undefined, row.description)} title="Editar"><Pencil size={16} className="icon" /></button>
                          <button onClick={() => deleteActivity.mutate(row.activityId)} disabled={deleteActivity.isPending} title="Eliminar"><Trash2 size={16} className="icon" /></button>
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

      <div className="history-cards">
        {filtered.map(row => {
          const isEditing = editingId === row.activityId && editingEmissionId === row.emissionId
          const isExpanded = expandedKey === row.key
          return (
            <div key={row.key} className="history-card">
              <div className="history-card__header">
                <span className="history-card__date">
                  <CalendarDays size={14} className="icon" />
                  {format(row.date, 'dd/MM/yyyy')}
                </span>
                <div className="history-card__header-actions">
                  {!isEditing && (
                    <button
                      className="history-card__chevron"
                      onClick={() => setExpandedKey(k => k === row.key ? null : row.key)}
                      title={isExpanded ? 'Contraer' : 'Expandir'}
                    >
                      {isExpanded ? <ChevronUp size={16} className="icon" /> : <ChevronDown size={16} className="icon" />}
                    </button>
                  )}
                  <div className="history-card__menu">
                    <button
                      className="history-card__menu-btn"
                      onClick={() => setOpenMenuKey(k => k === row.key ? null : row.key)}
                      title="Opciones"
                    >
                      <MoreVertical size={18} className="icon" />
                    </button>
                    {openMenuKey === row.key && (
                      <>
                        <div className="history-card__menu-overlay" onClick={() => setOpenMenuKey(null)} />
                        <div className="history-card__menu-popover">
                          <button
                            className="history-card__menu-item"
                            onClick={() => { startEdit(row.activity, row.emissionId ?? undefined, row.description); setOpenMenuKey(null) }}
                          >
                            <Pencil size={14} className="icon" /> Editar
                          </button>
                          <button
                            className="history-card__menu-item history-card__menu-item--danger"
                            disabled={deleteActivity.isPending}
                            onClick={() => { deleteActivity.mutate(row.activityId); setOpenMenuKey(null) }}
                          >
                            <Trash2 size={14} className="icon" /> Eliminar
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {isEditing ? (
                <div className="history-item__edit-form">
                  <input type="date" className="history-edit__date" value={editDate} onChange={e => setEditDate(e.target.value)} />
                  <p className="history-edit__text-readonly">{editText}</p>
                  {editUnit && (
                    <div className="history-edit__qty-row">
                      <input
                        type="number"
                        min="0"
                        step="any"
                        className="history-edit__qty"
                        value={editQuantity}
                        onChange={e => setEditQuantity(e.target.value)}
                      />
                      <span className="history-edit__unit">{editUnit}</span>
                    </div>
                  )}
                  <div className="history-edit__actions">
                    <button disabled={editActivity.isPending} onClick={() => saveEdit(row.activityId)}>
                      {editActivity.isPending ? 'Guardando…' : 'Guardar'}
                    </button>
                    <button className="btn-light" onClick={cancelEdit}>Cancelar</button>
                  </div>
                </div>
              ) : (
                <div className="history-card__body" onClick={() => setExpandedKey(k => k === row.key ? null : row.key)}>
                  <div className="history-card__title-row">
                    <CategoryIconBadge category={row.category} />
                    <div>
                      <h3 className="history-card__title">{row.description}</h3>
                      {row.category && (
                        <span className="emission-badge" style={categoryBadgeVars(row.category) as CSSProperties}>
                          {row.category}
                        </span>
                      )}
                    </div>
                  </div>
                  {isExpanded && (
                    <div className="admin-detail__meta history-card__details">
                      <div><span>Cantidad</span><span>{row.quantity || '—'}</span></div>
                      <div><span>CO₂e</span><span>{row.co2 !== null ? `${row.co2.toFixed(3)} kg` : '—'}</span></div>
                      <div><span>Categoría</span><span>{row.category || '—'}</span></div>
                      <div><span>Fecha y hora</span><span>{format(row.date, 'dd/MM/yyyy, HH:mm')}</span></div>
                    </div>
                  )}
                  <div className="history-card__divider" />
                  <div className="history-card__footer">
                    <span className="history-card__qty">{row.quantity || '—'}</span>
                    {row.co2 !== null
                      ? <span className="co2-badge" style={co2BadgeVars(row.co2) as CSSProperties}>{row.co2.toFixed(3)} kg</span>
                      : <span className="admin-table__placeholder">—</span>
                    }
                  </div>
                </div>
              )}
            </div>
          )
        })}
        {filtered.length === 0 && (
          <div className="panel-state">Sin resultados para esta búsqueda.</div>
        )}
      </div>
    </div>
  )
}
