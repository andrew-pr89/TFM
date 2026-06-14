import { useAuth0 } from '@auth0/auth0-react'

export function LoginPage() {
  const { loginWithRedirect, isLoading } = useAuth0()

  return (
    <div className="login-page">
      <div className="login-card">
        <img src="/logo.png" alt="Planet Pulse" className="login-card__logo-img" />
        <p className="login-card__subtitle">
          Tu asistente de huella de carbono personal
        </p>
        <button
          className="login-card__btn"
          onClick={() => loginWithRedirect()}
          disabled={isLoading}
        >
          {isLoading ? 'Cargando…' : 'Iniciar sesión'}
        </button>
        <p className="login-card__hint">
          Autenticación segura con Auth0
        </p>
      </div>
    </div>
  )
}
