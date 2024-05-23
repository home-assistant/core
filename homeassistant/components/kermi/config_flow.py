"""Config flow for kermi."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE

from .const import DOMAIN


class KermiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kermi."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Validate the user input using your own logic and update the errors dictionary if there are any errors
            # If the input is valid, create the config entry
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        # Provide default values only when user_input is not None
        default_host = user_input[CONF_HOST] if user_input else ""
        default_port = user_input[CONF_PORT] if user_input else 502
        default_type = user_input[CONF_TYPE] if user_input else "tcp"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=default_host): str,
                    vol.Required(CONF_PORT, default=default_port): vol.Coerce(int),
                    vol.Required("heatpump_device_address", default=40): int,
                    vol.Optional("climate_device_address", default=50): int,
                    vol.Optional("water_heater_device_address", default=51): int,
                    vol.Required(CONF_TYPE, default=default_type): str,
                }
            ),
            errors=errors,
        )
