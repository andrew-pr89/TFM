"""
Autenticación OAuth2 con Auth0.

Valida el JWT Bearer token usando las claves públicas JWKS de Auth0
y devuelve el `sub` del usuario como user_id.
"""

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings

_bearer = HTTPBearer(auto_error=False)
_jwks_cache: dict | None = None


def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is None:
        resp = httpx.get(
            f"https://{settings.auth0_domain}/.well-known/jwks.json",
            timeout=5,
        )
        resp.raise_for_status()
        _jwks_cache = resp.json()
    return _jwks_cache


ROLES_CLAIM = "https://planet-pulse-api/roles"


def _decode_token(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    jwks = _get_jwks()
    rsa_key = next(
        (k for k in jwks["keys"] if k["kid"] == header.get("kid")),
        None,
    )
    if rsa_key is None:
        raise HTTPException(status_code=401, detail="Clave JWT no encontrada")
    try:
        return jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.auth0_audience,
            issuer=f"https://{settings.auth0_domain}/",
        )
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Token inválido: {exc}")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    payload = _decode_token(credentials.credentials)
    return payload["sub"]


def get_admin_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    payload = _decode_token(credentials.credentials)
    roles: list[str] = payload.get(ROLES_CLAIM, [])
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="Se requiere rol de administrador")
    return payload["sub"]
