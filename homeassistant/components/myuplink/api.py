"""API for myUplink bound to Home Assistant OAuth."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from myuplink.auth_abstract import AbstractAuth

from .const import API_ENDPOINT

if TYPE_CHECKING:
    from aiohttp import ClientSession

    from homeassistant.helpers import config_entry_oauth2_flow


class AsyncConfigEntryAuth(AbstractAuth):
    """Provide myUplink authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize myUplink auth."""
        super().__init__(websession, API_ENDPOINT)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return cast(str, self._oauth_session.token["access_token"])
