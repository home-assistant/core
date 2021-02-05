"""Config flow for the Epson integration."""

from homeassistant import config_entries
from homeassistant.const import CONF_NAME

from .const import EPSON_DOMAIN as DOMAIN, PROJECTOR_CONFIG_FLOW_SCHEMA as DATA_SCHEMA


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Epson."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title=user_input.pop(CONF_NAME), data=user_input
            )
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
