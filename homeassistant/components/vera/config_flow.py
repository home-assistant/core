"""Config flow for Vera."""
from homeassistant import config_entries

from .const import CONF_BASE_URL, DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class VeraFlowHandler(config_entries.ConfigFlow):
    """Vera config flow."""

    async def async_step_import(self, config: dict):
        """Handle a flow initialized by import."""
        return self.async_create_entry(title=config.get(CONF_BASE_URL), data=config)
