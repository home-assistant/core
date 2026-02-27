"""Config flow for EDL21 integration."""

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import (
    CONF_SERIAL_PORT,
    CONF_UPDATE_INTERVAL,
    DEFAULT_TITLE,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_PORT): str,
    }
)


class EDL21ConfigFlow(ConfigFlow, domain=DOMAIN):
    """EDL21 config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow handler."""
        return EDL21OptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
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


class EDL21OptionsFlow(OptionsFlow):
    """EDL21 options flow."""

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                        ),
                    ): vol.All(int, vol.Range(min=1)),
                }
            ),
        )
