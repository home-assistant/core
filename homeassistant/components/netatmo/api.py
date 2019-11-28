"""API for Netatmo bound to HASS OAuth."""
from asyncio import run_coroutine_threadsafe
import logging

import pyatmo

from homeassistant import core, config_entries
from homeassistant.helpers import config_entry_oauth2_flow

_LOGGER = logging.getLogger(__name__)


class ConfigEntryNetatmoAuth(pyatmo.auth.NetatmOAuth2):
    """Provide Netatmo authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: core.HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        implementation: config_entry_oauth2_flow.AbstractOAuth2Implementation,
    ):
        """Initialize Netatmo Auth."""
        _LOGGER.debug("Netatmo ConfigEntryNetatmoAuth")
        self.hass = hass
        self.config_entry = config_entry
        _LOGGER.debug("Netatmo ConfigEntryAuth 2")
        self.session = config_entry_oauth2_flow.OAuth2Session(
            hass, config_entry, implementation
        )
        _LOGGER.debug("Netatmo ConfigEntryAuth 3")
        super().__init__(token=self.session.token)

    def refresh_tokens(self) -> dict:
        """Refresh and return new Netatmo tokens using Home Assistant OAuth2 session."""
        _LOGGER.debug("Netatmo ConfigEntryAuth.refresh_tokens")
        run_coroutine_threadsafe(
            self.session.async_ensure_token_valid(), self.hass.loop
        ).result()

        return self.session.token
