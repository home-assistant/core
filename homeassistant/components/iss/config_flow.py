"""Config flow to configure iss component."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_SHOW_ON_MAP
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .binary_sensor import DEFAULT_NAME
from .const import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for iss component."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initialized by the user."""
        # Check if already configured
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Check if location have been defined.
        if not self.hass.config.latitude and not self.hass.config.longitude:
            return self.async_abort(reason="latitude_longitude_not_defined")

        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, DEFAULT_NAME),
                data={},
                options={CONF_SHOW_ON_MAP: user_input.get(CONF_SHOW_ON_MAP, False)},
            )

        return self.async_show_form(step_id="user")


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options handler for iss."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None) -> FlowResult:
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
