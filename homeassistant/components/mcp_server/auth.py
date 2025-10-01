"""Authentication helpers for the FastMCP integration."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import cast

from pydantic import AnyHttpUrl

from homeassistant.core import HomeAssistant
from homeassistant.helpers import network

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings

from .const import DOMAIN


@dataclass(slots=True)
class FastMCPAuthConfig:
    """Container describing FastMCP authentication configuration."""

    settings: AuthSettings
    token_verifier: TokenVerifier


class HomeAssistantTokenVerifier(TokenVerifier):
    """Token verifier that delegates to Home Assistant's auth framework."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the token verifier."""
        self._hass = hass

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify a bearer token against Home Assistant's auth system."""
        refresh_token = self._hass.auth.async_validate_access_token(token)
        if refresh_token is None:
            return None

        client_id = refresh_token.client_id or "home-assistant"
        expires_at: int | None
        if refresh_token.expire_at is not None:
            expires_at = int(refresh_token.expire_at)
        elif refresh_token.access_token_expiration:
            expires_at = int(
                refresh_token.created_at.timestamp()
                + refresh_token.access_token_expiration.total_seconds()
            )
        else:
            expires_at = None

        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=[],
            expires_at=expires_at,
            resource=None,
        )


async def async_resolve_auth_config(hass: HomeAssistant) -> FastMCPAuthConfig:
    """Resolve auth settings and a token verifier for FastMCP."""

    base_url = await _async_detect_base_url(hass)
    issuer_url = f"{base_url}/auth"
    resource_url = f"{base_url}/{DOMAIN}"

    settings = AuthSettings(
        issuer_url=cast(AnyHttpUrl, issuer_url),
        resource_server_url=cast(AnyHttpUrl, resource_url),
        service_documentation_url=cast(AnyHttpUrl, "https://www.home-assistant.io/integrations/mcp_server"),
        required_scopes=None,
    )

    return FastMCPAuthConfig(
        settings=settings, token_verifier=HomeAssistantTokenVerifier(hass)
    )


async def _async_detect_base_url(hass: HomeAssistant) -> str:
    """Best-effort detection of the Home Assistant base URL."""

    for prefer_external in (True, False):
        try:
            get_url = partial(
                network.get_url,
                hass,
                allow_external=True,
                allow_internal=True,
                prefer_external=prefer_external,
            )
            return await hass.async_add_executor_job(get_url)
        except network.NoURLAvailableError:
            continue

    if hass.config.api is not None:
        scheme = "https" if hass.config.api.use_ssl else "http"
        host = hass.config.api.local_ip or "127.0.0.1"
        return f"{scheme}://{host}:{hass.config.api.port}"

    return "http://127.0.0.1:8123"
