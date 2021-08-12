"""Config flow for pvpc_hourly_pricing."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from . import CONF_NAME, UI_CONFIG_SCHEMA, VALID_POWER, VALID_TARIFF
from .const import ATTR_POWER, ATTR_POWER_P3, ATTR_TARIFF, DOMAIN


class TariffSelectorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for `pvpc_hourly_pricing`."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return PVPCOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[ATTR_TARIFF])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(step_id="user", data_schema=UI_CONFIG_SCHEMA)

    async def async_step_import(self, import_info):
        """Handle import from config file."""
        return await self.async_step_user(import_info)


class PVPCOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle PVPC options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Fill options with entry data
        tariff = self.config_entry.options.get(
            ATTR_TARIFF, self.config_entry.data[ATTR_TARIFF]
        )
        power = self.config_entry.options.get(
            ATTR_POWER, self.config_entry.data[ATTR_POWER]
        )
        power_valley = self.config_entry.options.get(
            ATTR_POWER_P3, self.config_entry.data[ATTR_POWER_P3]
        )
        schema = vol.Schema(
            {
                vol.Required(ATTR_TARIFF, default=tariff): VALID_TARIFF,
                vol.Required(ATTR_POWER, default=power): VALID_POWER,
                vol.Required(ATTR_POWER_P3, default=power_valley): VALID_POWER,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
