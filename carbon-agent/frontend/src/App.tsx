import { useState, useRef, useEffect, useCallback, type ReactNode } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import {
  MessageCircle, ClipboardList, Target, BarChart2,
  Leaf, SlidersHorizontal, ShieldCheck, Sun, Moon, MoreHorizontal,
} from 'lucide-react'
import { ChatBubble } from './components/ChatBubble'
import { ChatInput } from './components/ChatInput'
import { HistoryPanel } from './components/HistoryPanel'
import { SummaryPanel } from './components/SummaryPanel'
import { ImprovementsPanel } from './components/ImprovementsPanel'
import { DailyDashboard } from './components/DailyDashboard'
import { SettingsPanel, SETTINGS_SUBTABS, type SettingsSubTab } from './components/SettingsPanel'
import { LoginPage } from './components/LoginPage'
import { AdminPanel } from './components/AdminPanel'
import { useSettings } from './hooks/useSettings'
import { usePostActivity, useApplyRecurring } from './hooks/useCarbon'
import { useIsAdmin } from './hooks/useIsAdmin'
import { setupAuthInterceptor } from './services/api'
import type { ChatMessage } from './types'

type Tab = 'chat' | 'history' | 'dashboard' | 'summary' | 'improvements' | 'settings' | 'admin'

const NAV_ICON_PROPS = { size: 18, className: 'icon icon-nav' }

const BASE_NAV: { id: Tab; label: string; icon: ReactNode }[] = [
  { id: 'chat',         label: 'Chat',         icon: <MessageCircle  {...NAV_ICON_PROPS} /> },
  { id: 'history',      label: 'Historial',    icon: <ClipboardList  {...NAV_ICON_PROPS} /> },
  { id: 'dashboard',    label: 'Hoy',          icon: <Target         {...NAV_ICON_PROPS} /> },
  { id: 'summary',      label: 'Estadísticas', icon: <BarChart2      {...NAV_ICON_PROPS} /> },
  { id: 'improvements', label: 'Mejoras',      icon: <Leaf           {...NAV_ICON_PROPS} /> },
  { id: 'settings',     label: 'Ajustes',      icon: <SlidersHorizontal {...NAV_ICON_PROPS} /> },
]

// Items shown in the mobile bottom nav (primary)
const PRIMARY_NAV_IDS: Tab[] = ['chat', 'history', 'dashboard', 'summary', 'improvements']
// Items hidden behind the "more" button on mobile
const MORE_NAV_IDS: Tab[] = ['settings', 'admin']

const ADMIN_NAV = { id: 'admin' as Tab, label: 'Admin', icon: <ShieldCheck {...NAV_ICON_PROPS} /> as ReactNode }

let msgCounter = 0
const uid = () => `msg-${++msgCounter}`

export default function App() {
  const { isAuthenticated, isLoading, getAccessTokenSilently, logout, user } = useAuth0()
  const isAdmin = useIsAdmin()
  const NAV_ITEMS = isAdmin ? [...BASE_NAV, ADMIN_NAV] : BASE_NAV
  const [tab, setTab] = useState<Tab>('chat')
  const [settingsTab, setSettingsTab] = useState<SettingsSubTab>('goal')
  const [lightTheme, setLightTheme] = useState(true)
  const [moreOpen, setMoreOpen] = useState(false)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', lightTheme ? 'light' : 'dark')
  }, [lightTheme])
  const { annualGoalKg } = useSettings()
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: uid(),
      role: 'assistant',
      text: '¡Hola! Soy tu asistente de huella de carbono. Cuéntame qué actividades has hecho hoy y calcularé su impacto en CO₂.',
      timestamp: new Date(),
    },
  ])
  const [pendingContext, setPendingContext] = useState<{ originalText: string; question: string } | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const mutation = usePostActivity()
  const applyRecurring = useApplyRecurring()

  useEffect(() => {
    if (isAuthenticated) applyRecurring.mutate()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated])

  // Configura el interceptor de axios con el token de Auth0
  useEffect(() => {
    if (!isAuthenticated) return
    setupAuthInterceptor(() =>
      getAccessTokenSilently({
        authorizationParams: { audience: import.meta.env.VITE_AUTH0_AUDIENCE },
      })
    )
  }, [isAuthenticated, getAccessTokenSilently])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = useCallback(async (text: string) => {
    const userMsg: ChatMessage = { id: uid(), role: 'user', text, timestamp: new Date() }
    setMessages((prev) => [...prev, userMsg])

    try {
      const data = await mutation.mutateAsync(text)
      if (data.is_question) {
        setPendingContext({ originalText: pendingContext?.originalText ?? text, question: data.message })
      } else if (data.clarifying_question) {
        setPendingContext({ originalText: text, question: data.clarifying_question })
      } else {
        setPendingContext(null)
      }
      const assistantMsg: ChatMessage = {
        id: uid(),
        role: 'assistant',
        text: data.message,
        data,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch {
      setPendingContext(null)
      setMessages((prev) => [
        ...prev,
        {
          id: uid(),
          role: 'error',
          text: 'No pude conectar con el servidor. Comprueba que el backend está corriendo.',
          timestamp: new Date(),
        },
      ])
    }
  }, [mutation, pendingContext])

  if (isLoading) {
    return (
      <div className="login-page">
        <div className="login-card">
          <div>🌿</div>
          <p className="login-card__subtitle">Cargando…</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <LoginPage />
  }

  return (
    <div className="app">
      {/* ── Sidebar (desktop) ── */}
      <nav className="sidebar">
        <div className="sidebar__brand">
          <img src="/logo.png" alt="Planet Pulse" className="sidebar__logo-img" />
        </div>
        <ul className="sidebar__nav">
          {NAV_ITEMS.map((item) => (
            <li key={item.id}>
              <button
                className={`nav-item ${tab === item.id ? 'nav-item--active' : ''}`}
                onClick={() => setTab(item.id)}
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </button>
              {item.id === 'settings' && tab === 'settings' && (
                <ul className="nav-subtabs">
                  {SETTINGS_SUBTABS.map((s) => (
                    <li key={s.id}>
                      <button
                        className={`nav-subitem ${settingsTab === s.id ? 'nav-subitem--active' : ''}`}
                        onClick={() => setSettingsTab(s.id)}
                      >
                        <span>{s.icon}</span>
                        <span>{s.label}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
        <div className="sidebar__footer">
          <div className="user-info">
            {user?.picture && (
              <img className="user-info__avatar" src={user.picture} alt={user.name} />
            )}
            <div className="user-info__text fs-sm">
              <span className="user-info__name">{user?.name ?? user?.email}</span>
              {user?.name && user?.email && (
                <span className="user-info__email">{user.email}</span>
              )}
            </div>
          </div>
          <button
            className="btn-light"
            onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
          >
            Cerrar sesión
          </button>
        </div>
      </nav>

      {/* ── Theme toggle (fixed top-right) ── */}
      <div className="theme-toggle-fixed">
        <button
          className="contrast-toggle"
          onClick={() => setLightTheme(v => !v)}
          title={lightTheme ? 'Cambiar a tema oscuro' : 'Cambiar a tema claro'}
        >
          {lightTheme ? <Moon size={15} className="icon" /> : <Sun size={15} className="icon" />}
          <span className="contrast-toggle__label">{lightTheme ? 'Oscuro' : 'Claro'}</span>
        </button>
      </div>

      {/* ── Main content ── */}
      <main className="main">
        <header className="topbar">
          <h1 className="topbar__title">
            {tab === 'settings'
              ? SETTINGS_SUBTABS.find(s => s.id === settingsTab)?.label
              : NAV_ITEMS.find((n) => n.id === tab)?.label
            }
          </h1>
        </header>

        <div className="content">
          {tab === 'chat' && (
            <div className="chat-layout">
              <div className="chat-messages">
                {messages.map((msg) => (
                  <ChatBubble key={msg.id} message={msg} />
                ))}
                {mutation.isPending && (
                  <div className="bubble bubble--assistant bubble--thinking">
                    <span className="dot" /><span className="dot" /><span className="dot" />
                  </div>
                )}
                <div ref={bottomRef} />
              </div>
              <div className="chat-input-area">
                <ChatInput onSend={handleSend} isLoading={mutation.isPending} />
              </div>
            </div>
          )}

          {tab === 'history' && (
            <div className="panel-layout">
              <HistoryPanel />
            </div>
          )}

          {tab === 'dashboard' && (
            <div className="dashboard-layout">
              <DailyDashboard annualGoalKg={annualGoalKg} />
            </div>
          )}

          {tab === 'summary' && (
            <div className="panel-layout">
              <SummaryPanel annualGoalKg={annualGoalKg} />
            </div>
          )}

          {tab === 'improvements' && (
            <div className="panel-layout">
              <ImprovementsPanel annualGoalKg={annualGoalKg} />
            </div>
          )}

          {tab === 'settings' && (
            <div className="panel-layout">
              <SettingsPanel tab={settingsTab} lightTheme={lightTheme} onToggleTheme={() => setLightTheme(v => !v)} />
            </div>
          )}

          {tab === 'admin' && isAdmin && (
            <div className="panel-layout">
              <AdminPanel />
            </div>
          )}
        </div>
      </main>

      {/* ── Bottom nav (mobile only) ── */}
      {moreOpen && (
        <div className="more-overlay" onClick={() => setMoreOpen(false)}>
          <div className="more-sheet" onClick={e => e.stopPropagation()}>
            {NAV_ITEMS.filter(i => MORE_NAV_IDS.includes(i.id)).map(item => (
              <button
                key={item.id}
                className={`more-sheet__item ${tab === item.id ? 'more-sheet__item--active' : ''}`}
                onClick={() => { setTab(item.id); setMoreOpen(false) }}
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}
      <nav className="bottom-nav">
        {NAV_ITEMS.filter(i => PRIMARY_NAV_IDS.includes(i.id)).map((item) => (
          <button
            key={item.id}
            className={`bottom-nav__item ${tab === item.id ? 'bottom-nav__item--active' : ''}`}
            onClick={() => setTab(item.id)}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
        <button
          className={`bottom-nav__item ${MORE_NAV_IDS.includes(tab) ? 'bottom-nav__item--active' : ''}`}
          onClick={() => setMoreOpen(v => !v)}
        >
          <span><MoreHorizontal {...NAV_ICON_PROPS} /></span>
          <span>Más</span>
        </button>
      </nav>
    </div>
  )
}
