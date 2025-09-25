"""Application credentials platform for the Level Lock integration.

We use a PKCE implementation so this integration does not require a
client secret. Each Home Assistant instance will generate its own
code_verifier per authorization flow.
"""

from __future__ import annotations

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

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


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return a PKCE-enabled OAuth implementation.

    We intentionally ignore any provided client secret and use the
    LocalOAuth2ImplementationWithPkce which does not require a secret.
    """
    auth_server = await async_get_authorization_server(hass)
    return config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce(
        hass,
        auth_domain,
        credential.client_id,
        auth_server.authorize_url,
        auth_server.token_url,
        credential.client_secret or "",
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog.

    Inform users that PKCE is used and a client secret is not required.
    """
    return {
        "client_secret_note": "Client secret is optional for Level Lock (PKCE). If provided, it will be used during token exchange.",
    }
