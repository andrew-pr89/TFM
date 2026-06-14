import { useState, useRef, useEffect, useCallback } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import { ChatBubble } from './components/ChatBubble'
import { ChatInput } from './components/ChatInput'
import { HistoryPanel } from './components/HistoryPanel'
import { SummaryPanel } from './components/SummaryPanel'
import { ImprovementsPanel } from './components/ImprovementsPanel'
import { DailyDashboard } from './components/DailyDashboard'
import { SettingsPanel } from './components/SettingsPanel'
import { LoginPage } from './components/LoginPage'
import { useSettings } from './hooks/useSettings'
import { usePostActivity } from './hooks/useCarbon'
import { setupAuthInterceptor } from './services/api'
import type { ChatMessage } from './types'

type Tab = 'chat' | 'history' | 'dashboard' | 'summary' | 'improvements' | 'settings'

const NAV_ITEMS: { id: Tab; label: string; icon: string }[] = [
  { id: 'chat',         label: 'Chat',         icon: '💬' },
  { id: 'history',      label: 'Historial',    icon: '📋' },
  { id: 'dashboard',    label: 'Hoy',          icon: '🎯' },
  { id: 'summary',      label: 'Estadísticas', icon: '📊' },
  { id: 'improvements', label: 'Mejoras',      icon: '🌱' },
  { id: 'settings',     label: 'Ajustes',      icon: '⚙️' },
]

let msgCounter = 0
const uid = () => `msg-${++msgCounter}`

export default function App() {
  const { isAuthenticated, isLoading, getAccessTokenSilently, logout, user } = useAuth0()
  const [tab, setTab] = useState<Tab>('chat')
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
          <div className="login-card__logo">🌿</div>
          <p style={{ color: 'var(--text-muted)' }}>Cargando…</p>
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
                <span className="nav-item__icon">{item.icon}</span>
                <span className="nav-item__label">{item.label}</span>
              </button>
            </li>
          ))}
        </ul>
        <div className="sidebar__footer">
          <div className="user-info">
            {user?.picture && (
              <img className="user-info__avatar" src={user.picture} alt={user.name} />
            )}
            <div className="user-info__text">
              <span className="user-info__name">{user?.name ?? user?.email}</span>
              {user?.name && user?.email && (
                <span className="user-info__email">{user.email}</span>
              )}
            </div>
          </div>
          <button
            className="logout-btn"
            onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
          >
            Cerrar sesión
          </button>
        </div>
      </nav>

      {/* ── Main content ── */}
      <main className="main">
        <header className="topbar">
          <h1 className="topbar__title">
            {NAV_ITEMS.find((n) => n.id === tab)?.icon}{' '}
            {NAV_ITEMS.find((n) => n.id === tab)?.label}
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
            <div className="panel-layout">
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
              <SettingsPanel />
            </div>
          )}
        </div>
      </main>

      {/* ── Bottom nav (mobile only) ── */}
      <nav className="bottom-nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`bottom-nav__item ${tab === item.id ? 'bottom-nav__item--active' : ''}`}
            onClick={() => setTab(item.id)}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
    </div>
  )
}
