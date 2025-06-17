"""API for Google bound to Home Assistant OAuth."""

from typing import cast

from aiohttp import ClientSession
from google_air_quality_api import api

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session


class AsyncConfigEntryAuth(api.AbstractAuth):
    """Provide Google authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: OAuth2Session,
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
        websession: ClientSession,
        token: str,
    ) -> None:
        """Initialize ConfigFlowAuth."""
        super().__init__(websession)
        self._token = token

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        return self._token
