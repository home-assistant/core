"""Application credentials for the Lepro integration."""

import time
from typing import Any

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import AUTH_CALLBACK_PATH

from .const import DOMAIN


class LoproOAuth2Implementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """OAuth2 implementation that uses the local HA callback, bypassing My HA."""

    @property
    def redirect_uri(self) -> str:
        """Return local redirect URI from the current request's HA base URL."""
        from homeassistant.components import http  # noqa: PLC0415

        if req := http.current_request.get():
            if ha_host := req.headers.get(
                config_entry_oauth2_flow.HEADER_FRONTEND_BASE
            ):
                return f"{ha_host}{AUTH_CALLBACK_PATH}"
        return config_entry_oauth2_flow.async_get_redirect_uri(self.hass)

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve auth code to token, converting absolute expires_in to relative seconds."""
        token = await super().async_resolve_external_data(external_data)
        if "expires_in" in token:
            token["expires_in"] = max(0, int(token["expires_in"]) - int(time.time()))
        return token

    async def async_refresh_token(self, token: dict) -> dict:
        """Refresh token, handling server's absolute expires_in timestamp."""
        new_token = await self._async_refresh_token(token)
        if "expires_in" in new_token:
            expires_abs = int(new_token["expires_in"])
            new_token["expires_in"] = max(0, expires_abs - int(time.time()))
            new_token["expires_at"] = float(expires_abs)
        else:
            new_token["expires_in"] = 3600
            new_token["expires_at"] = time.time() + 3600
        return new_token


async def async_get_auth_implementation(
    hass: HomeAssistant,
    auth_domain: str,
    credential: ClientCredential,
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return a custom OAuth2 implementation using the resolved API host."""
    api_host = hass.data.get(DOMAIN, {}).get("api_host", "")
    return LoproOAuth2Implementation(
        hass,
        auth_domain,
        credential.client_id,
        credential.client_secret,
        f"{api_host}/oauth2/web/login.html",
        f"{api_host}/oauth2/token",
    )
