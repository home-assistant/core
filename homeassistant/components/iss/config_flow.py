"""Config flow to configure iss component."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_SHOW_ON_MAP
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for iss component."""

    VERSION = 1

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
                title="International Space Station", data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SHOW_ON_MAP, default=False): bool,
                }
            ),
        )

    async def async_step_import(self, conf: dict) -> FlowResult:
        """Import a configuration from configuration.yaml."""
        return await self.async_step_user(
            user_input={
                CONF_NAME: conf[CONF_NAME],
                CONF_SHOW_ON_MAP: conf[CONF_SHOW_ON_MAP],
            }
        )
