"""Config flow to configure the sun integration."""
from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN


@callback
def configured_instances(hass):
    """Return a set of configured Notion instances."""
    return set(entry.entry_id for entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class SunFlowHandler(config_entries.ConfigFlow):
    """Handle a sun config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_ASSUMED

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if configured_instances(self.hass):
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="Default", data={})
