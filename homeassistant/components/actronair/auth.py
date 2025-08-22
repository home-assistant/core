"""ActronAir API authentication using Home Assistant's OAuth2 integration."""

from typing import cast

from actronair_api import ACP_BASE_URL, AbstractAuth
from aiohttp import ClientSession

from homeassistant.helpers import config_entry_oauth2_flow


class AsyncConfigEntryAuth(AbstractAuth):
    """Authentication handler for ActronAir using Home Assistant OAuth2 session."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize the authentication handler with OAuth2 session and base URL."""
        super().__init__(websession, ACP_BASE_URL)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Ensure the OAuth2 access token is valid and return it. Refreshes the token if expired and returns the active access token as a string."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return cast(str, self._oauth_session.token["access_token"])
