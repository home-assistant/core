import asyncio
import logging
import voluptuous as vol
import async_timeout
from collections import OrderedDict
from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback
from homeassistant.const import (CONF_TIME_ZONE, CONF_USERNAME, CONF_PASSWORD)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@callback
def configured_instances(hass):
    """Return already configured instances"""
    entries = hass.config_entries.async_entries(DOMAIN)
    if entries:
        return entries[0]
    return None

@config_entries.HANDLERS.register(DOMAIN)
class VeSyncFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow"""
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Instantiate config flow"""
        self._username = None
        self._password = None
        self._time_zone = None
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
        """Handle external yaml configuration"""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle a flow start"""
        
        if configured_instances(self.hass) is not None:
            return self.async_abort({CONF_USERNAME: 'identifier_exists'})

        if not user_input:
            return await self._show_form()
        
        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]
        self._time_zone = user_input.get(CONF_TIME_ZONE, None)

        return await self.async_step_final()

    async def async_step_final(self):
            return self.async_create_entry(
                title=self._username,
                data={
                    CONF_USERNAME: self.username,
                    CONF_PASSWORD: self.password,
                    CONF_TIME_ZONE: self.time_zone,
            },
        )