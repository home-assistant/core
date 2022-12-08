"""Config flow for Home Assistant Supervisor integration."""
import logging

from homeassistant import config_entries

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant Supervisor."""

    VERSION = 1

    async def async_step_system(self, user_input=None):
        """Handle the initial step."""
        # We only need one Hass.io config entry
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Supervisor", data={})
