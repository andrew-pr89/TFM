import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { carbonApi } from '../services/api'
import type { UnknownItemOut, EmissionFactorCreate, EmissionFactorOut, EmissionFactorPatch } from '../types'

const MAIN_CATEGORIES = ['Alimentación', 'Transporte', 'Energía', 'Residuos', 'Compras', 'Ocio']
const UNITS = ['kg', 'km', 'kWh', 'litro', 'hora', 'unidad']
const SOURCE_TYPES = ['official', 'scientific_literature', 'estimated']
const STATUS_TABS = ['pending', 'added', 'rejected', 'all'] as const
type StatusTab = typeof STATUS_TABS[number]
type AdminSection = 'unknown' | 'factors'

const STATUS_LABEL: Record<string, string> = {
  pending: 'Pendiente',
  added: 'Añadido',
  rejected: 'Rechazado',
  all: 'Todos',
}

const STATUS_CLASS: Record<string, string> = {
  pending: 'status--pending',
  added: 'status--added',
  rejected: 'status--rejected',
}

const EMPTY_FACTOR: EmissionFactorCreate = {
  category: '',
  main_category: 'Alimentación',
  display_name: '',
  unit: 'unidad',
  factor_kg_co2e: 0,
  default_quantity: null,
  source_name: '',
  source_year: null,
  source_type: 'estimated',
  source_detail: '',
  source_url: '',
  notes: '',
}

function slugify(str: string) {
  return str.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '')
}

const GUESSED_TO_MAIN: Record<string, string> = {
  alimento: 'Alimentación',
  transporte: 'Transporte',
  energia: 'Energía',
  residuos: 'Residuos',
  compra: 'Compras',
  ocio: 'Ocio',
}

// ── Factor form (shared for create and edit) ──────────────────────────────────

interface FactorFormProps {
  initial: EmissionFactorCreate
  editId?: number
  onSave: (f: EmissionFactorCreate) => void
  onCancel: () => void
  isSaving: boolean
  showCategory?: boolean
}

function FactorForm({ initial, onSave, onCancel, isSaving, showCategory = true }: FactorFormProps) {
  const [form, setForm] = useState<EmissionFactorCreate>(initial)
  const set = (key: keyof EmissionFactorCreate, value: unknown) =>
    setForm(prev => ({ ...prev, [key]: value }))

  const handleDisplayName = (v: string) => {
    set('display_name', v)
    if (showCategory && (!form.category || form.category === slugify(initial.display_name ?? ''))) {
      set('category', slugify(v))
    }
  }

  return (
    <div className="admin-form">
      <div className="admin-form__grid">
        <label className="admin-form__field">
          <span>Nombre visible *</span>
          <input value={form.display_name} onChange={e => handleDisplayName(e.target.value)} placeholder="ej: Pechuga de pollo" />
        </label>

        {showCategory && (
          <label className="admin-form__field">
            <span>Categoría interna (slug) *</span>
            <input value={form.category} onChange={e => set('category', e.target.value)} placeholder="ej: pollo_pechuga" />
          </label>
        )}

        <label className="admin-form__field">
          <span>Categoría principal *</span>
          <select value={form.main_category} onChange={e => set('main_category', e.target.value)}>
            {MAIN_CATEGORIES.map(c => <option key={c}>{c}</option>)}
          </select>
        </label>

        <label className="admin-form__field">
          <span>Unidad *</span>
          <select value={form.unit} onChange={e => set('unit', e.target.value)}>
            {UNITS.map(u => <option key={u}>{u}</option>)}
          </select>
        </label>

        <label className="admin-form__field">
          <span>Factor kg CO₂e / unidad *</span>
          <input type="number" step="0.0001" min="0" value={form.factor_kg_co2e}
            onChange={e => set('factor_kg_co2e', parseFloat(e.target.value) || 0)} />
        </label>

        <label className="admin-form__field">
          <span>Ración estándar ({form.unit || 'unidad'})</span>
          <input
            type="number" step="0.001" min="0"
            placeholder="Sin valor = preguntará al usuario"
            value={form.default_quantity ?? ''}
            onChange={e => set('default_quantity', e.target.value ? parseFloat(e.target.value) : null)}
          />
        </label>

        <label className="admin-form__field">
          <span>Tipo de fuente</span>
          <select value={form.source_type ?? ''} onChange={e => set('source_type', e.target.value || null)}>
            <option value="">—</option>
            {SOURCE_TYPES.map(t => <option key={t}>{t}</option>)}
          </select>
        </label>

        <label className="admin-form__field">
          <span>Fuente</span>
          <input value={form.source_name ?? ''} onChange={e => set('source_name', e.target.value || null)} placeholder="IPCC, MITECO…" />
        </label>

        <label className="admin-form__field">
          <span>Año</span>
          <input type="number" value={form.source_year ?? ''} onChange={e => set('source_year', e.target.value ? parseInt(e.target.value) : null)} placeholder="2023" />
        </label>

        <label className="admin-form__field admin-form__field--full">
          <span>Detalle de fuente</span>
          <input value={form.source_detail ?? ''} onChange={e => set('source_detail', e.target.value || null)} placeholder="Tabla 3.2, Annex II…" />
        </label>

        <label className="admin-form__field admin-form__field--full">
          <span>URL fuente</span>
          <input value={form.source_url ?? ''} onChange={e => set('source_url', e.target.value || null)} placeholder="https://…" />
        </label>

        <label className="admin-form__field admin-form__field--full">
          <span>Notas</span>
          <textarea rows={2} value={form.notes ?? ''} onChange={e => set('notes', e.target.value || null)} />
        </label>
      </div>

      <div className="admin-form__actions">
        <button className="btn-light" onClick={onCancel}>Cancelar</button>
        <button
          disabled={isSaving || !form.display_name || form.factor_kg_co2e <= 0 || (showCategory && !form.category)}
          onClick={() => onSave(form)}
        >
          {isSaving ? 'Guardando…' : 'Guardar'}
        </button>
      </div>
    </div>
  )
}

// ── Factors CRUD panel ────────────────────────────────────────────────────────

function FactorsPanel() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [activeCategory, setActiveCategory] = useState<string>('all')
  const [editFactor, setEditFactor] = useState<EmissionFactorOut | null>(null)
  const [showCreate, setShowCreate] = useState(false)

  const { data: factors = [], isLoading } = useQuery({
    queryKey: ['admin-factors', search],
    queryFn: () => carbonApi.listFactors(search),
    staleTime: 30_000,
  })

  const createMutation = useMutation({
    mutationFn: (payload: EmissionFactorCreate) => carbonApi.createFactor(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-factors'] })
      setShowCreate(false)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: EmissionFactorPatch }) =>
      carbonApi.updateFactor(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-factors'] })
      setEditFactor(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => carbonApi.deleteFactor(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-factors'] })
      setEditFactor(null)
    },
  })

  const allCategories = useMemo(() => {
    const cats = new Set(factors.map(f => f.main_category))
    return ['all', ...MAIN_CATEGORIES.filter(c => cats.has(c)), ...Array.from(cats).filter(c => !MAIN_CATEGORIES.includes(c))]
  }, [factors])

  const filtered = useMemo(() =>
    activeCategory === 'all' ? factors : factors.filter(f => f.main_category === activeCategory),
    [factors, activeCategory]
  )

  const toEditForm = (f: EmissionFactorOut): EmissionFactorCreate => ({
    category: f.category,
    main_category: f.main_category,
    display_name: f.display_name,
    unit: f.unit,
    factor_kg_co2e: f.factor_kg_co2e,
    default_quantity: f.default_quantity,
    source_name: f.source_name,
    source_year: f.source_year,
    source_type: f.source_type,
    source_detail: f.source_detail,
    source_url: f.source_url,
    notes: f.notes,
  })

  if (showCreate) {
    return (
      <div className="admin-factors__create">
        <div className="admin-factors__create-header">
          <h3>Nuevo factor de emisión</h3>
        </div>
        <FactorForm
          initial={EMPTY_FACTOR}
          onSave={f => createMutation.mutate(f)}
          onCancel={() => setShowCreate(false)}
          isSaving={createMutation.isPending}
          showCategory
        />
      </div>
    )
  }

  if (editFactor) {
    return (
      <div className="admin-factors__create">
        <div className="admin-factors__create-header">
          <h3>Editar: <code>{editFactor.category}</code></h3>
        </div>
        <FactorForm
          initial={toEditForm(editFactor)}
          onSave={f => updateMutation.mutate({ id: editFactor.id, payload: f })}
          onCancel={() => setEditFactor(null)}
          isSaving={updateMutation.isPending}
          showCategory={false}
        />
        <div className="admin-factors__delete-zone">
          <button
            className="admin-factors__delete-btn"
            disabled={deleteMutation.isPending}
            onClick={() => {
              if (confirm(`¿Eliminar el factor "${editFactor.display_name}"? Esta acción no se puede deshacer.`)) {
                deleteMutation.mutate(editFactor.id)
              }
            }}
          >
            {deleteMutation.isPending ? 'Eliminando…' : 'Eliminar factor'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="admin-factors">
      <div className="admin-factors__toolbar">
        <input
          className="admin-search"
          placeholder="Buscar por nombre, slug o categoría…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <button onClick={() => setShowCreate(true)}>
          + Nuevo factor
        </button>
      </div>

      <div className="admin-tabs">
        {allCategories.map(cat => (
          <button
            key={cat}
            className={`tab-btn ${activeCategory === cat ? 'tab-btn--active' : ''}`}
            onClick={() => setActiveCategory(cat)}
          >
            {cat === 'all' ? 'Todos' : cat}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="panel-state">Cargando…</div>
      ) : filtered.length === 0 ? (
        <div className="panel-state">
          <span className="panel-state__icon">📭</span>
          <p>No hay factores{search ? ' que coincidan con la búsqueda' : ''}.</p>
        </div>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Slug</th>
              <th>Categoría</th>
              <th>Factor CO₂e</th>
              <th>Unidad</th>
              <th>Ración estándar</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(f => (
              <tr key={f.id} className="admin-table__row" onClick={() => setEditFactor(f)}>
                <td className="admin-table__term">{f.display_name}</td>
                <td><code className="admin-table__slug">{f.category}</code></td>
                <td className="admin-table__cat">{f.main_category}</td>
                <td className="admin-table__num">{f.factor_kg_co2e.toFixed(4)}</td>
                <td>{f.unit}</td>
                <td className="admin-table__num">
                  {f.default_quantity != null ? `${f.default_quantity} ${f.unit}` : <span className="admin-table__placeholder">—</span>}
                </td>
                <td onClick={e => e.stopPropagation()}>
                  <button
                    className="admin-delete-btn"
                    title="Eliminar"
                    disabled={deleteMutation.isPending}
                    onClick={() => {
                      if (confirm(`¿Eliminar "${f.display_name}"?`)) {
                        deleteMutation.mutate(f.id)
                      }
                    }}
                  >✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="admin-factors__count">{filtered.length} factor{filtered.length !== 1 ? 'es' : ''}</p>
    </div>
  )
}

// ── Unknown items panel ───────────────────────────────────────────────────────

function UnknownItemsPanel() {
  const queryClient = useQueryClient()
  const [statusTab, setStatusTab] = useState<StatusTab>('pending')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [activeItem, setActiveItem] = useState<UnknownItemOut | null>(null)
  const [showForm, setShowForm] = useState(false)

  const queryStatus = statusTab === 'all' ? 'pending' : statusTab

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['admin-unknown', statusTab],
    queryFn: () => statusTab === 'all'
      ? Promise.all([
          carbonApi.getUnknownItems('pending'),
          carbonApi.getUnknownItems('added'),
          carbonApi.getUnknownItems('rejected'),
        ]).then(([a, b, c]) => [...a, ...b, ...c])
      : carbonApi.getUnknownItems(queryStatus),
    staleTime: 30_000,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => carbonApi.deleteUnknownItem(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-unknown'] })
      setActiveItem(null)
      setSelected(new Set())
    },
  })

  const batchDeleteMutation = useMutation({
    mutationFn: (ids: number[]) => carbonApi.batchDeleteUnknownItems(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-unknown'] })
      setSelected(new Set())
    },
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      carbonApi.updateUnknownItemStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-unknown'] }),
  })

  const createFactorMutation = useMutation({
    mutationFn: (payload: EmissionFactorCreate) => carbonApi.createFactor(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-unknown'] })
      queryClient.invalidateQueries({ queryKey: ['admin-factors'] })
      if (activeItem) {
        statusMutation.mutate({ id: activeItem.id, status: 'added' })
      }
      setShowForm(false)
      setActiveItem(null)
    },
  })

  const filtered = useMemo(() =>
    items.filter(i =>
      i.raw_term.toLowerCase().includes(search.toLowerCase()) ||
      (i.context ?? '').toLowerCase().includes(search.toLowerCase()) ||
      (i.guessed_category ?? '').toLowerCase().includes(search.toLowerCase())
    ), [items, search])

  const allSelected = filtered.length > 0 && filtered.every(i => selected.has(i.id))
  const toggleAll = () => {
    if (allSelected) setSelected(new Set())
    else setSelected(new Set(filtered.map(i => i.id)))
  }
  const toggleOne = (id: number) => {
    const next = new Set(selected)
    next.has(id) ? next.delete(id) : next.add(id)
    setSelected(next)
  }

  const openItem = (item: UnknownItemOut) => {
    setActiveItem(item)
    setShowForm(false)
  }

  const initialFactor: EmissionFactorCreate = {
    ...EMPTY_FACTOR,
    display_name: activeItem?.raw_term ?? '',
    category: slugify(activeItem?.raw_term ?? ''),
    main_category: GUESSED_TO_MAIN[activeItem?.guessed_category ?? ''] ?? 'Alimentación',
  }

  return (
    <div className="admin-panel">
      <div className="admin-tabs">
        {STATUS_TABS.map(tab => (
          <button
            key={tab}
            className={`tab-btn ${statusTab === tab ? 'tab-btn--active' : ''}`}
            onClick={() => { setStatusTab(tab); setSelected(new Set()) }}
          >
            {STATUS_LABEL[tab]}
          </button>
        ))}
      </div>

      <div className="admin-toolbar">
        <input
          className="admin-search"
          placeholder="Buscar por término, contexto o categoría…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        {selected.size > 0 && (
          <button
            disabled={batchDeleteMutation.isPending}
            onClick={() => batchDeleteMutation.mutate([...selected])}
          >
            {batchDeleteMutation.isPending ? 'Eliminando…' : `Eliminar ${selected.size} seleccionados`}
          </button>
        )}
      </div>

      <div className="admin-content">
        <div className={`admin-table-wrap ${activeItem ? 'admin-table-wrap--narrow' : ''}`}>
          {isLoading ? (
            <div className="panel-state">Cargando…</div>
          ) : filtered.length === 0 ? (
            <div className="panel-state">
              <span className="panel-state__icon">✅</span>
              <p>No hay items {statusTab !== 'all' ? STATUS_LABEL[statusTab].toLowerCase() + 's' : ''}.</p>
            </div>
          ) : (
            <table className="admin-table">
              <thead>
                <tr>
                  <th><input type="checkbox" checked={allSelected} onChange={toggleAll} /></th>
                  <th>Término</th>
                  <th>Categoría sugerida</th>
                  <th>Estado</th>
                  <th>Fecha</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(item => (
                  <tr
                    key={item.id}
                    className={`admin-table__row ${activeItem?.id === item.id ? 'admin-table__row--active' : ''}`}
                    onClick={() => openItem(item)}
                  >
                    <td onClick={e => e.stopPropagation()}>
                      <input type="checkbox" checked={selected.has(item.id)} onChange={() => toggleOne(item.id)} />
                    </td>
                    <td className="admin-table__term">{item.raw_term}</td>
                    <td className="admin-table__cat">{item.guessed_category ?? '—'}</td>
                    <td>
                      <span className={`admin-status-badge ${STATUS_CLASS[item.status]}`}>
                        {STATUS_LABEL[item.status]}
                      </span>
                    </td>
                    <td className="admin-table__date">
                      {format(new Date(item.created_at), 'd MMM yy', { locale: es })}
                    </td>
                    <td onClick={e => e.stopPropagation()}>
                      <button
                        className="admin-delete-btn"
                        title="Eliminar"
                        disabled={deleteMutation.isPending}
                        onClick={() => deleteMutation.mutate(item.id)}
                      >✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {activeItem && (
          <div className="admin-detail">
            <div className="admin-detail__header">
              <h3>{activeItem.raw_term}</h3>
              <button className="admin-detail__close" onClick={() => { setActiveItem(null); setShowForm(false) }}>✕</button>
            </div>

            <div className="admin-detail__meta">
              <div><span>Estado</span>
                <span className={STATUS_CLASS[activeItem.status]}>{STATUS_LABEL[activeItem.status]}</span>
              </div>
              <div><span>Categoría sugerida</span><span>{activeItem.guessed_category ?? '—'}</span></div>
              <div><span>Usuario</span><span className="admin-detail__userid">{activeItem.user_id}</span></div>
              <div><span>Fecha</span><span>{format(new Date(activeItem.created_at), "d MMM yyyy, HH:mm", { locale: es })}</span></div>
            </div>

            {activeItem.context && (
              <div className="admin-detail__context">
                <span>Contexto original</span>
                <p>{activeItem.context}</p>
              </div>
            )}

            <div className="admin-detail__actions">
              {activeItem.status === 'pending' && (
                <>
                  <button
                    className="btn-light"
                    onClick={() => { statusMutation.mutate({ id: activeItem.id, status: 'rejected' }); setActiveItem(null) }}
                  >
                    Rechazar
                  </button>
                  <button onClick={() => setShowForm(true)}>
                    Crear factor de emisión
                  </button>
                </>
              )}
              <button
                className="admin-delete-btn"
                onClick={() => deleteMutation.mutate(activeItem.id)}
                disabled={deleteMutation.isPending}
              >
                Eliminar
              </button>
            </div>

            {showForm && (
              <FactorForm
                initial={initialFactor}
                onSave={f => createFactorMutation.mutate(f)}
                onCancel={() => setShowForm(false)}
                isSaving={createFactorMutation.isPending}
                showCategory
              />
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main admin panel ──────────────────────────────────────────────────────────

export function AdminPanel() {
  const [section, setSection] = useState<AdminSection>('unknown')

  return (
    <div className="admin-panel">
      <div className="admin-panel__header">
        <h2>Panel de administración</h2>
        <div className="admin-section-tabs">
          <button
            className={`tab-btn ${section === 'unknown' ? 'tab-btn--active' : ''}`}
            onClick={() => setSection('unknown')}
          >
            Items desconocidos
          </button>
          <button
            className={`tab-btn ${section === 'factors' ? 'tab-btn--active' : ''}`}
            onClick={() => setSection('factors')}
          >
            Factores de emisión
          </button>
        </div>
      </div>

      {section === 'unknown' ? <UnknownItemsPanel /> : <FactorsPanel />}
    </div>
  )
}
