"""API for Netatmo bound to HASS OAuth."""
from asyncio import run_coroutine_threadsafe

from aiohttp import ClientSession
import pyatmo

from homeassistant import config_entries, core
from homeassistant.helpers import config_entry_oauth2_flow


class ConfigEntryNetatmoAuth(pyatmo.auth.NetatmoOAuth2):
    """Provide Netatmo authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: core.HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        implementation: config_entry_oauth2_flow.AbstractOAuth2Implementation,
    ):
        """Initialize Netatmo Auth."""
        self.hass = hass
        self.session = config_entry_oauth2_flow.OAuth2Session(
            hass, config_entry, implementation
        )
        super().__init__(token=self.session.token)

    def refresh_tokens(
        self,
    ) -> dict:
        """Refresh and return new Netatmo tokens using Home Assistant OAuth2 session."""
        run_coroutine_threadsafe(
            self.session.async_ensure_token_valid(), self.hass.loop
        ).result()

        return self.session.token


class AsyncConfigEntryNetatmoAuth(pyatmo.auth.AbstractAsyncAuth):
    """Provide Netatmo authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ):
        """Initialize the auth."""
        super().__init__(websession)
        self._oauth_session = oauth_session

    async def async_get_access_token(self):
        """Return a valid access token for SDM API."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()
        return self._oauth_session.token["access_token"]
