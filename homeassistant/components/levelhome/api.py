"""Home Assistant OAuth2 glue for Level Lock."""

from __future__ import annotations

from asyncio import run_coroutine_threadsafe
from aiohttp import ClientSession

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow


# Library client and errors now live in client.py


class ConfigEntryAuth:
    """Provide Level Lock authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Level Lock Auth."""
        self.hass = hass
        self.session = oauth_session

    def refresh_tokens(self) -> str:
        """Refresh and return new Level Lock tokens using Home Assistant OAuth2 session."""
        run_coroutine_threadsafe(
            self.session.async_ensure_token_valid(), self.hass.loop
        ).result()

        return self.session.token["access_token"]


class AsyncConfigEntryAuth:
    """Provide Level Lock authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Level Lock auth."""
        self._websession = websession
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self._oauth_session.async_ensure_token_valid()
        return self._oauth_session.token["access_token"]
