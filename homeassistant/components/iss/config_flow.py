"""Config flow to configure iss component."""

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_SHOW_ON_MAP
from homeassistant.core import callback

from .const import DEFAULT_NAME, DOMAIN


class ISSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for iss component."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={},
                options={CONF_SHOW_ON_MAP: user_input.get(CONF_SHOW_ON_MAP, False)},
            )

        return self.async_show_form(step_id="user")


class OptionsFlowHandler(OptionsFlow):
    """Config flow options handler for iss."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SHOW_ON_MAP,
                        default=self.config_entry.options.get(CONF_SHOW_ON_MAP, False),
                    ): bool,
                }
            ),
        )
