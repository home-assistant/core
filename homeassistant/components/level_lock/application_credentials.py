"""Application credentials platform for the Level Lock integration."""

from __future__ import annotations

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant

from .const import (
    CONF_OAUTH2_BASE_URL,
    DEFAULT_OAUTH2_BASE_URL,
    DOMAIN,
    OAUTH2_AUTHORIZE_PATH,
    OAUTH2_TOKEN_EXCHANGE_PATH,
)


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server.

    The OAuth2 and partner server base URLs may be provided via configuration.yaml:

    level_lock:
      oauth2_base_url: https://oauth2.example.com
      partner_base_url: https://partner.example.com
    """
    base = (hass.data.get(DOMAIN) or {}).get(
        CONF_OAUTH2_BASE_URL
    ) or DEFAULT_OAUTH2_BASE_URL
    return AuthorizationServer(
        authorize_url=f"{base}{OAUTH2_AUTHORIZE_PATH}",
        token_url=f"{base}{OAUTH2_TOKEN_EXCHANGE_PATH}",
    )
