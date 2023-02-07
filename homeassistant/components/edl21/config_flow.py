"""Config flow for EDL21 integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_SERIAL_PORT, DOMAIN


class EDL21ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """EDL21 config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the user setup step."""
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_SERIAL_PORT: user_input[CONF_SERIAL_PORT],
                }
            )
            self._async_abort_entries_match(
                {
                    CONF_NAME: user_input[CONF_NAME],
                }
            )

            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        data_schema = {
            vol.Required(CONF_NAME): str,
            vol.Required(CONF_SERIAL_PORT): str,
        }

        return self.async_show_form(step_id="user", data_schema=vol.Schema(data_schema))
