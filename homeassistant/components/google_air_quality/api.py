"""API for Google Photos bound to Home Assistant OAuth."""

from typing import cast

import aiohttp
from google_air_quality_api import api

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow


class AsyncConfigEntryAuth(api.AbstractAuth):
    """Provide Google Photos authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: aiohttp.ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize AsyncConfigEntryAuth."""
        super().__init__(websession)
        self._session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self._session.async_ensure_token_valid()
        return cast(str, self._session.token[CONF_ACCESS_TOKEN])


class AsyncConfigFlowAuth(api.AbstractAuth):
    """An API client used during the config flow with a fixed token."""

    def __init__(
        self,
        websession: aiohttp.ClientSession,
        token: str,
    ) -> None:
        """Initialize ConfigFlowAuth."""
        super().__init__(websession)
        self._token = token

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        return self._token
