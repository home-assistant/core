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
    CONF_PARTNER_BASE_URL,
    DEFAULT_OAUTH2_BASE_URL,
    DEFAULT_PARTNER_BASE_URL,
    DOMAIN,
    OAUTH2_AUTHORIZE_PATH,
    OAUTH2_TOKEN_EXCHANGE_PATH,
)


class LevelOAuth2Implementation(
    config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce
):
    """Level Lock OAuth2 implementation with PKCE support for token refresh.

    Level uses the device code flow where token refresh happens via the
    OAuth2 server's /v1/token/exchange endpoint with grant_type=refresh_token.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        client_id: str,
        authorize_url: str,
        token_url: str,
        client_secret: str,
        partner_token_url: str,
    ) -> None:
        """Initialize with both OAuth2 and partner server token URLs."""
        super().__init__(
            hass, domain, client_id, authorize_url, token_url, client_secret
        )
        self._partner_token_url = partner_token_url
        # Clear client_secret for PKCE flows
        self.client_secret = ""

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh tokens using the OAuth2 server's token exchange endpoint."""
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "refresh_token": token["refresh_token"],
        }
        if code_verifier := token.get("code_verifier"):
            data["code_verifier"] = code_verifier

        new_token = await self._token_request(data)

        if code_verifier:
            new_token["code_verifier"] = code_verifier
        return {**token, **new_token}


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server.

    The OAuth2 and partner server base URLs may be provided via configuration.yaml:

    levelhome:
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
    LevelOAuth2Implementation which includes code_verifier in token refresh.
    Token refresh uses the OAuth2 server's token exchange endpoint.
    """
    auth_server = await async_get_authorization_server(hass)
    partner_base = (hass.data.get(DOMAIN) or {}).get(
        CONF_PARTNER_BASE_URL
    ) or DEFAULT_PARTNER_BASE_URL
    partner_token_url = f"{partner_base}{OAUTH2_TOKEN_EXCHANGE_PATH}"

    return LevelOAuth2Implementation(
        hass,
        auth_domain,
        credential.client_id,
        auth_server.authorize_url,
        auth_server.token_url,
        credential.client_secret or "",
        partner_token_url,
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog.

    Inform users that PKCE is used and a client secret is not required.
    """
    return {
        "client_secret_note": "Client secret is optional for Level Lock (PKCE). If provided, it will be used during token exchange.",
    }
