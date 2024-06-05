"""Config flow for kermi."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class KermiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kermi."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_setup_entry(self, entry: ConfigEntry) -> bool:
        """Set up a config entry."""
        # Set the unique ID of the config flow to the entry_id of the config entry
        await self.async_set_unique_id(entry.entry_id)
        return True

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # If the input is valid, create the config entry
            if not errors:
                entry = self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )
                self._abort_if_unique_id_configured()
                return entry

        # Provide default values only when user_input is not None
        default_host = user_input[CONF_HOST] if user_input else ""

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=default_host): str,
                    vol.Required("heatpump_device_address", default=40): int,
                    vol.Optional("climate_device_address", default=50): int,
                    vol.Optional("water_heater_device_address", default=51): int,
                }
            ),
            errors=errors,
        )
