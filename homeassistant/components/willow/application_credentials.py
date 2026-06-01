"""Application credentials platform for the Willow integration."""

from typing import Any

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    LocalOAuth2Implementation,
)

from .const import OAUTH2_AUTHORIZE, OAUTH2_TOKEN

DEFAULT_EXPIRES_IN = 10 * 365 * 24 * 60 * 60


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return auth implementation."""
    return WillowOAuth2Implementation(
        hass,
        auth_domain,
        credential.client_id,
        credential.client_secret,
        OAUTH2_AUTHORIZE,
        OAUTH2_TOKEN,
    )


class WillowOAuth2Implementation(LocalOAuth2Implementation):
    """Willow OAuth2 implementation."""

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        token = await super().async_resolve_external_data(external_data)
        return self._normalize_token(token)

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh a token."""
        if not token.get("refresh_token"):
            return token

        new_token = await super()._async_refresh_token(token)
        return self._normalize_token(new_token)

    def _normalize_token(self, token: dict) -> dict:
        """Normalize Willow token response."""
        if token.get("expires_in") is None:
            token["expires_in"] = DEFAULT_EXPIRES_IN

        return token
