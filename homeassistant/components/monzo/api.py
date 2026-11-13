"""API for Monzo bound to Home Assistant OAuth."""

from typing import override

from aiohttp import ClientSession
from monzopy import AbstractMonzoApi

from homeassistant.helpers import config_entry_oauth2_flow


class AuthenticatedMonzoAPI(AbstractMonzoApi):
    """A Monzo API instance with authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Monzo auth."""
        super().__init__(websession)
        self._oauth_session = oauth_session

    @override
    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self._oauth_session.async_ensure_token_valid()

        return str(self._oauth_session.token["access_token"])


class MonzoAPI(AbstractMonzoApi):
    """A Monzo API instance using a static access token."""

    def __init__(self, websession: ClientSession, access_token: str) -> None:
        """Initialize Monzo auth."""
        super().__init__(websession)
        self._access_token = access_token

    @override
    async def async_get_access_token(self) -> str:
        """Return the access token."""
        return self._access_token
