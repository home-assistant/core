from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol
from .sensor import DOMAIN, CONF_SERIAL_PORT
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

from typing import Any

EDL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_PORT): cv.string,
        vol.Optional(CONF_NAME, default=""): cv.string,
    }
)


class EDL21ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EDL21."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle a flow initiated by the user."""
        if user_input is not None:
            self.data = user_input
            return self.async_create_entry(title="EDL21", data=self.data)

        return self.async_show_form(step_id="user", data_schema=EDL_SCHEMA)
