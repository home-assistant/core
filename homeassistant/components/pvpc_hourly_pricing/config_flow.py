"""Config flow for pvpc_hourly_pricing."""
from homeassistant import config_entries

from . import CONF_NAME, UI_CONFIG_SCHEMA
from .const import ATTR_TARIFF, DOMAIN

_DOMAIN_NAME = DOMAIN


class TariffSelectorConfigFlow(config_entries.ConfigFlow, domain=_DOMAIN_NAME):
    """Handle a config flow for `pvpc_hourly_pricing` to select the tariff."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

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
