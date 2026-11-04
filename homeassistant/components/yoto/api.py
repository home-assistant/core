"""API for Yoto bound to Home Assistant OAuth."""

from typing import cast, override

from yoto_api import AbstractAuth

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session


class AsyncConfigEntryAuth(AbstractAuth):
    """Provide Yoto authentication tied to an OAuth2 based config entry."""

    def __init__(self, oauth_session: OAuth2Session) -> None:
        """Initialize Yoto auth."""
        self._oauth_session = oauth_session

    @override
    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self._oauth_session.async_ensure_token_valid()
        return cast(str, self._oauth_session.token[CONF_ACCESS_TOKEN])
