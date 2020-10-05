"""API for Smappee bound to Home Assistant OAuth."""
from asyncio import run_coroutine_threadsafe

from pysmappee import api

from homeassistant import config_entries, core
from homeassistant.const import CONF_PLATFORM
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN


class ConfigEntrySmappeeApi(api.SmappeeApi):
    """Provide Smappee authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: core.HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        implementation: config_entry_oauth2_flow.AbstractOAuth2Implementation,
    ):
        """Initialize Smappee Auth."""
        self.hass = hass
        self.config_entry = config_entry
        self.session = config_entry_oauth2_flow.OAuth2Session(
            hass, config_entry, implementation
        )

        platform_to_farm = {
            "PRODUCTION": 1,
            "ACCEPTANCE": 2,
            "DEVELOPMENT": 3,
        }
        super().__init__(
            None,
            None,
            token=self.session.token,
            farm=platform_to_farm[hass.data[DOMAIN][CONF_PLATFORM]],
        )

    def refresh_tokens(self) -> dict:
        """Refresh and return new Smappee tokens using Home Assistant OAuth2 session."""
        run_coroutine_threadsafe(
            self.session.async_ensure_token_valid(), self.hass.loop
        ).result()

        return self.session.token
