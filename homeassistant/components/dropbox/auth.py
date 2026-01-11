"""Authentication for Dropbox."""

from typing import cast

from aiohttp import ClientSession
from python_dropbox_api import Auth

from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session


class AsyncConfigEntryAuth(Auth):
    """Provide Dropbox authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: OAuth2Session,
    ) -> None:
        """Initialize AsyncConfigEntryAuth."""
        super().__init__(websession)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self._oauth_session.async_ensure_token_valid()

        return cast(str, self._oauth_session.token["access_token"])


class AsyncConfigFlowAuth(Auth):
    """Provide authentication tied to a fixed token for the config flow."""

    def __init__(
        self,
        websession: ClientSession,
        token: str,
    ) -> None:
        """Initialize AsyncConfigFlowAuth."""
        super().__init__(websession)
        self._token = token

    async def async_get_access_token(self) -> str:
        """Return the fixed access token."""
        return self._token
