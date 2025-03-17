"""API for Actron Air bound to Home Assistant OAuth."""

from typing import cast

from actronair_api import ACP_BASE_URL, AbstractAuth
from aiohttp import ClientSession

from homeassistant.helpers import config_entry_oauth2_flow


class AsyncConfigEntryAuth(AbstractAuth):  # my_pypi_package.AbstractAuth):
    """Provide actronair authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Actron Air auth."""
        super().__init__(websession, ACP_BASE_URL)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return cast(str, self._oauth_session.token["access_token"])
