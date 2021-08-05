"""API for Netatmo bound to HASS OAuth."""
from typing import cast

from aiohttp import ClientSession
import pyatmo

from homeassistant.helpers import config_entry_oauth2_flow


class AsyncConfigEntryNetatmoAuth(pyatmo.auth.AbstractAsyncAuth):
    """Provide Netatmo authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize the auth."""
        super().__init__(websession)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token for Netatmo API."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()
        return cast(str, self._oauth_session.token["access_token"])
