"""API for nVent RAYCHEM SENZ bound to Home Assistant OAuth."""

from typing import cast

from aiosenz import AbstractSENZAuth
from httpx import AsyncClient

from homeassistant.helpers import config_entry_oauth2_flow


class SENZConfigEntryAuth(AbstractSENZAuth):
    """Provide nVent RAYCHEM SENZ authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        httpx_async_client: AsyncClient,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize SENZ auth."""
        super().__init__(httpx_async_client)
        self._oauth_session = oauth_session

    async def get_access_token(self) -> str:
        """Return a valid access token."""
        await self._oauth_session.async_ensure_token_valid()
        return cast(str, self._oauth_session.token["access_token"])
