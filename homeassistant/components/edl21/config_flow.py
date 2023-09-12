"""Config flow for EDL21 integration."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_SERIAL_PORT, DEFAULT_TITLE, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_PORT): str,
    }
)


class EDL21ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """EDL21 config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the user setup step."""
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_SERIAL_PORT: user_input[CONF_SERIAL_PORT]}
            )

            return self.async_create_entry(
                title=DEFAULT_TITLE,
                data=user_input,
            )

        data_schema = self.add_suggested_values_to_schema(DATA_SCHEMA, user_input)
        return self.async_show_form(step_id="user", data_schema=data_schema)
