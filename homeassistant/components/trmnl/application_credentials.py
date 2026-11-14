"""Application credentials platform for the TRMNL integration."""

from typing import Any, override

from aiohttp import ClientError

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2ImplementationWithPkce,
)

from .const import (
    CLIENT_ID,
    LOGGER,
    OAUTH2_AUTHORIZE,
    OAUTH2_REVOKE,
    OAUTH2_SCOPES,
    OAUTH2_TOKEN,
)


class TRMNLOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """TRMNL OAuth2 implementation."""

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Ask for the capabilities the integration uses."""
        return {"scope": OAUTH2_SCOPES, **super().extra_authorize_data}


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> TRMNLOAuth2Implementation:
    """Return the TRMNL OAuth2 implementation."""
    return TRMNLOAuth2Implementation(
        hass, auth_domain, credential.client_id, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
    )


async def async_revoke_token(hass: HomeAssistant, access_token: str) -> None:
    """Revoke a token Home Assistant will not keep, so no connection is left at TRMNL."""
    try:
        async with async_get_clientsession(hass).post(
            OAUTH2_REVOKE, data={"token": access_token, "client_id": CLIENT_ID}
        ) as response:
            response.raise_for_status()
    except ClientError, TimeoutError:
        LOGGER.warning("Could not revoke an unused TRMNL token")
