"""Config flow for Soma."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import (
    CONF_HOST, CONF_PORT)
from .const import DOMAIN, HOST, PORT

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 3000


@callback
def register_flow_implementation(hass, host, port):
    """Register a flow implementation."""
    hass.data[DOMAIN][HOST] = host
    hass.data[DOMAIN][PORT] = port


@config_entries.HANDLERS.register('soma')
class SomaFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Instantiate config flow."""
        self.device_config = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        _LOGGER.info('Soma setup flow started...')

        if user_input is None:
            data = {vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int
                    }

            return self.async_show_form(
                step_id='user',
                description_placeholders=self.device_config,
                data_schema=vol.Schema(data)
            )

        return await self.async_step_creation(user_input)

    async def async_step_creation(self, user_input=None):
        """Finish config flow."""
        from api.soma_api import SomaApi
        api = SomaApi(user_input['host'])
        await self.hass.async_add_executor_job(
            api.list_devices)
        _LOGGER.info('Successfully set up Soma Connect')
        return self.async_create_entry(
            title='Soma Connect',
            data={
                'host': user_input['host'],
                'port': user_input['port']
            },
        )
