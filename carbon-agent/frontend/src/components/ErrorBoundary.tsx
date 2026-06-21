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
        <div className="error-boundary">
          
          <h2>Algo ha ido mal</h2>
          <p>
            La aplicación ha encontrado un error inesperado.
            Recarga la página para intentarlo de nuevo.
          </p>
          <pre className="error-boundary__message">{this.state.message}</pre>
          <button className="btn-light" onClick={() => window.location.reload()}>
            Recargar
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
