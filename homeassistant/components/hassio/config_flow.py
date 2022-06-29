"""Config flow for Home Assistant Supervisor integration."""
from homeassistant import config_entries

from . import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant Supervisor."""

    VERSION = 1

    async def async_step_system(self, user_input=None):
        """Handle the initial step."""
        # We only need one Hass.io config entry
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return self.async_create_entry(title="Supervisor", data={})
