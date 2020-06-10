"""API for Smappee Official bound to Home Assistant OAuth."""
from asyncio import run_coroutine_threadsafe

from pysmappee import api

from homeassistant import config_entries, core
from homeassistant.helpers import config_entry_oauth2_flow


class ConfigEntrySmappeeApi(api.SmappeeApi):
    """Provide Smappee Official authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: core.HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        implementation: config_entry_oauth2_flow.AbstractOAuth2Implementation,
    ):
        """Initialize Smappee Official Auth."""
        self.hass = hass
        self.config_entry = config_entry
        self.session = config_entry_oauth2_flow.OAuth2Session(
            hass, config_entry, implementation
        )
        super().__init__(None, None, token=self.session.token)

    def refresh_tokens(self) -> dict:
        """Refresh and return new Smappee Official tokens using Home Assistant OAuth2 session."""
        run_coroutine_threadsafe(
            self.session.async_ensure_token_valid(), self.hass.loop
        ).result()

        return self.session.token
