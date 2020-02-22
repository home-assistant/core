"""Config flow for pvpc_hourly_pricing."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from . import CONF_NAME, UI_CONFIG_SCHEMA
from .const import ATTR_TARIFF, DOMAIN, TARIFFS


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle the Options flow for `pvpc_hourly_pricing` to change the tariff."""

    def __init__(self, entry: config_entries.ConfigEntry):
        """Initialize the options flow handler with the config entry to modify."""
        self.config_entry = entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.config_entry.data.get(CONF_NAME), data=user_input,
            )

        current_tariff = self.config_entry.data.get(ATTR_TARIFF)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required(ATTR_TARIFF, default=current_tariff): vol.In(TARIFFS)}
            ),
        )


class TariffSelectorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for `pvpc_hourly_pricing` to select the tariff."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            if any(
                user_input[CONF_NAME] == entry.data[CONF_NAME]
                for entry in self._async_current_entries()
            ):
                return self.async_abort(reason="already_configured")

            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(step_id="user", data_schema=UI_CONFIG_SCHEMA)

    async def async_step_import(self, import_info):
        """Handle import from config file."""
        return await self.async_step_user(import_info)

    @staticmethod
    @callback
    def async_get_options_flow(entry: config_entries.ConfigEntry):
        """Handle tariff change via Options panel."""
        return OptionsFlowHandler(entry)
