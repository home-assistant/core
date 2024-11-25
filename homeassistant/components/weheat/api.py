"""API for Weheat bound to Home Assistant OAuth."""

from aiohttp import ClientSession
from weheat.abstractions import AbstractAuth

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from .const import API_URL


class AsyncConfigEntryAuth(AbstractAuth):
    """Provide Weheat authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: OAuth2Session,
    ) -> None:
        """Initialize Weheat auth."""
        super().__init__(websession, host=API_URL)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token[CONF_ACCESS_TOKEN]
