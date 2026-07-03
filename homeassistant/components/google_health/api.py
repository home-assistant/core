"""API for Google Health bound to Home Assistant OAuth."""

from typing import cast

from aiohttp import ClientSession
from google_health_api.auth import AbstractAuth

from homeassistant.helpers import config_entry_oauth2_flow


class AsyncConfigEntryAuth(AbstractAuth):  # type: ignore[misc]
    """Provide Google Health authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Google Health auth."""
        super().__init__(websession)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self._oauth_session.async_ensure_token_valid()

        return cast(str, self._oauth_session.token["access_token"])


class SimpleAuth(AbstractAuth):  # type: ignore[misc]
    """Temporary auth helper for the config flow."""

    def __init__(self, websession: ClientSession, access_token: str) -> None:
        """Initialize the auth helper."""
        super().__init__(websession)
        self._access_token = access_token

    async def async_get_access_token(self) -> str:
        """Return the access token."""
        return self._access_token
