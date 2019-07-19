"""Config flow for Soma."""
import asyncio
import logging

import async_timeout

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback
from homeassistant.const import (
    CONF_DEVICE, CONF_HOST, CONF_MAC, CONF_NAME, CONF_PASSWORD, CONF_PORT,
    CONF_USERNAME)
from .const import DOMAIN, HOST, PORT

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 3000

@callback
def register_flow_implementation(hass, host, port):
    """Register a flow implementation.

    """
    hass.data[DOMAIN][HOST] = host
    hass.data[DOMAIN][PORT] = port


@config_entries.HANDLERS.register('soma')
class SomaFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Instantiate config flow."""
        self.device_config = {}

    async def async_step_import(self, user_input=None):
        """Handle external yaml configuration."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason='already_setup')
        return await self.async_step_auth()

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        _LOGGER.info('Soma setup flow started...')
       
        if user_input is None:
            data = { vol.Required(CONF_HOST): str,
                     vol.Required(CONF_PORT, default=DEFAULT_PORT): int
                   }
         
            return self.async_show_form(
                step_id='user',
                description_placeholders=self.device_config,
                data_schema=vol.Schema(data)
            )

        return await self.async_step_creation(user_input)

    async def async_step_creation(self, user_input=None):
        _LOGGER.info('Successfully set up Soma Connect')
        return self.async_create_entry(
            title='Soma Connect',
            data={
                'host': user_input['host'],
                'port': user_input['port']
            },
        )

