"""API for Minut Point bound to Home Assistant OAuth."""

from aiohttp import ClientSession
import pypoint

from homeassistant.helpers import config_entry_oauth2_flow


class AsyncConfigEntryAuth(pypoint.AbstractAuth):
    """Provide Minut Point authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Minut Point auth."""
        super().__init__(websession)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]
