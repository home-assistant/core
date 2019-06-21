import asyncio
import logging
import voluptuous as vol
import async_timeout
from collections import OrderedDict
from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback
from .const import DOMAIN
from homeassistant.const import (CONF_TIME_ZONE, CONF_USERNAME, CONF_PASSWORD)

_LOGGER = logging.getLogger(__name__)


@callback
def configured_instances(hass):
    """Return already configured instances"""
    return set(
        entry.data[CONF_USERNAME]
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


@config_entries.HANDLERS.register(DOMAIN)
class VeSyncFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow"""
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Instantiate config flow"""
        self.data_schema = OrderedDict()
        self.data_schema[vol.Required(CONF_USERNAME)] = str
        self.data_schema[vol.Required(CONF_PASSWORD)] = str
        self.data_schema[vol.Optional(CONF_TIME_ZONE)] = str

    async def _show_form(self, errors=None):
        """Show form to the user"""
        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema(self.data_schema),
            errors=errors if errors else {},
        )

    async def async_step_import(self, import_config):
        """Handle extername yaml configuration"""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle a flow start"""

        if not user_input:
            return await self._show_form()

        if user_input[CONF_USERNAME] in configured_instances(self.hass):
            return await self._show_form({CONF_USERNAME: 'identifier_exists'})

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        time_zone = user_input[CONF_TIME_ZONE]

        return self.async_create_entry(
            title=user_input[CONF_USERNAME],
            data={
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
                CONF_TIME_ZONE: time_zone,
            }
        )