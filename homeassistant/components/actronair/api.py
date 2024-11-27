"""API for Actron Air bound to Home Assistant OAuth."""

from asyncio import run_coroutine_threadsafe

from aiohttp import ClientSession

# import my_pypi_package
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow


class ConfigEntryAuth:  # (my_pypi_package.AbstractAuth):
    """Provide actronair authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize actronair Auth."""
        self.hass = hass
        self.session = oauth_session
        # super().__init__(self.session.token)

    def refresh_tokens(self) -> str:
        """Refresh and return new actronair tokens using Home Assistant OAuth2 session."""
        run_coroutine_threadsafe(
            self.session.async_ensure_token_valid(), self.hass.loop
        ).result()

        return self.session.token["access_token"]


class AsyncConfigEntryAuth:  # my_pypi_package.AbstractAuth):
    """Provide actronair authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize trial auth."""
        # super().__init__(websession)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]
