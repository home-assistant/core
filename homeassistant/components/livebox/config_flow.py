"""Config flow to configure Livebox."""
import asyncio
import json
import os

import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import (
    DOMAIN, LOGGER, 
    DEFAULT_USERNAME, DEFAULT_HOST, DEFAULT_PORT,
    TEMPLATE_SENSOR)
from .errors import AuthenticationRequired, CannotConnect

@callback
def configured_hosts(hass):
    """Return a set of the configured hosts."""
    return set(entry.data['host'] for entry
               in hass.config_entries.async_entries(DOMAIN))

@config_entries.HANDLERS.register(DOMAIN)
class LiveboxFlowHandler(config_entries.ConfigFlow):
    """Handle a Livebox config flow."""

    VERSION = 1
    # CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the Livebox flow."""
        self.host = None
        self.port = None
        self.username = None 
        self.password = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        # Use OrderedDict to guarantee order of the form shown to the user
        from collections import OrderedDict 
        
        data_schema = OrderedDict()
        data_schema[vol.Optional('host',default=DEFAULT_HOST)] = str
        data_schema[vol.Optional('port', default=DEFAULT_PORT)] = str
        data_schema[vol.Optional('username', default=DEFAULT_USERNAME)] = str
        data_schema[vol.Required('password')] = str

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema(data_schema)
        )


    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        if user_input is not None:
            self.host = user_input['host']
            self.port = user_input['port']
            self.username = user_input['username']
            self.password = user_input['password']
            return await self.async_step_link()

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema(data_schema),
        )

    async def async_step_link(self, user_input=None):
        errors = {}

        from aiosysbus import Sysbus
        
        try:
            box = Sysbus()
            await box.open(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password)
            return await self._entry_from_box(box)

        except AuthenticationRequired:
            errors['base'] = 'register_failed'

        except CannotConnect:
            LOGGER.error("Error connecting to the Livebox at %s", self.host)
            errors['base'] = 'linking'

        except Exception:  # pylint: disable=broad-except
            LOGGER.exception(
                'Unknown error connecting with Livebox at %s',
                self.host)
            errors['base'] = 'linking'

        # If there was no user input, do not show the errors.
        if user_input is None:
            errors = {}

        return self.async_show_form(
            step_id='link',
            errors=errors,
        )    

    async def _entry_from_box(self, box):
        """Return a config entry from an initialized box."""
        config = await box.system.get_deviceinfo()
        box_id = config['status']['SerialNumber']

        # Remove all other entries of hubs with same ID or host
        same_hub_entries = [entry.entry_id for entry
                            in self.hass.config_entries.async_entries(DOMAIN)
                            if entry.data['box_id'] == box_id]

        if same_hub_entries:
            await asyncio.wait([self.hass.config_entries.async_remove(entry_id)
                                for entry_id in same_hub_entries])

        return self.async_create_entry(
            title=TEMPLATE_SENSOR.format(''),
            data={
                'box_id': box_id,
                'host': self.host,
                'port': self.port,
                'username': self.username,
                'password': self.password
            }
        )