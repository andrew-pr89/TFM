from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"

    # Base de datos
    database_url: str = "sqlite:///./carbon_agent.db"

    # App
    app_env: str = "development"
    app_debug: bool = True

    # CORS — URL del frontend en producción (Railway/Vercel/Netlify)
    # Ejemplo: https://carbon-agent.vercel.app
    frontend_url: str = ""

    # Admin — token para endpoints protegidos (cámbialo en .env en producción)
    admin_token: str = "change-me"

    # Auth0 — JWT validation
    auth0_domain: str = ""
    auth0_audience: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
