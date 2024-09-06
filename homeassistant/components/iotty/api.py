"""API for iotty bound to Home Assistant OAuth."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientSession
from iottycloud.cloudapi import CloudApi

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

OAUTH2_CLIENT_ID = "hass-iotty"
IOTTYAPI_BASE = "https://homeassistant.iotty.com/"


class IottyProxy(CloudApi):
    """Provide iotty authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize iotty auth."""

        super().__init__(websession, IOTTYAPI_BASE, OAUTH2_CLIENT_ID)
        if oauth_session is None:
            raise ValueError("oauth_session")
        self._oauth_session = oauth_session
        self._hass = hass

    async def async_get_access_token(self) -> Any:
        """Return a valid access token."""

        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]
