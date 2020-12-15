"""Config flow for wiz_light."""
from homeassistant.data_entry_flow import AbortFlow
import logging

import voluptuous as vol
from pywizlight import wizlight

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME

from .const import DOMAIN, DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WiZ Light."""

    VERSION = 1
    config = {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    }

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            try:
                bulb = wizlight(user_input[CONF_IP_ADDRESS])
                mac = await bulb.getMac()
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
            except AbortFlow:
                return self.async_abort(reason="single_instance_allowed")

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(self.config), errors=errors
        )

    async def async_step_import(self, import_config):
        """Import from config."""
        return await self.async_step_user(user_input=import_config)
