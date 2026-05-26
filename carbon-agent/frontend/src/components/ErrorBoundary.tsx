import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  message: string
}

/**
 * Captura errores de renderizado de React para evitar pantalla negra en producción.
 * Los hooks no pueden hacer esto — necesita ser una clase.
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, message: '' }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          gap: '1rem',
          padding: '2rem',
          background: '#0f172a',
          color: '#e2e8f0',
          fontFamily: 'sans-serif',
          textAlign: 'center',
        }}>
          <span style={{ fontSize: '3rem' }}>⚠️</span>
          <h2 style={{ color: '#f87171', margin: 0 }}>Algo ha ido mal</h2>
          <p style={{ color: '#94a3b8', maxWidth: '400px' }}>
            La aplicación ha encontrado un error inesperado.
            Recarga la página para intentarlo de nuevo.
          </p>
          <pre style={{
            background: '#1e293b',
            padding: '0.75rem 1rem',
            borderRadius: '8px',
            fontSize: '0.75rem',
            color: '#fb923c',
            maxWidth: '100%',
            overflowX: 'auto',
          }}>
            {this.state.message}
          </pre>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '0.5rem 1.5rem',
              borderRadius: '8px',
              border: 'none',
              background: '#4ade80',
              color: '#0f172a',
              fontWeight: 600,
              cursor: 'pointer',
              fontSize: '0.9rem',
            }}
          >
            Recargar
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
