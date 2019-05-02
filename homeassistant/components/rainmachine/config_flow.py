"""Config flow to configure the RainMachine component."""
from collections import OrderedDict

from regenmaschine import Client
from regenmaschine.errors import RainMachineError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import (
    CONF_EMAIL, CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_SCAN_INTERVAL,
    CONF_SSL, CONF_TYPE)
from homeassistant.helpers import aiohttp_client

from .const import DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DEFAULT_SSL, DOMAIN

DROPDOWN_LOCAL = 'Via IP Address'
DROPDOWN_REMOTE = 'Via RainMachine Cloud'

TYPE_LOCAL = 'local'
TYPE_REMOTE = 'remote'


@callback
def configured_instances(hass):
    """Return a set of configured RainMachine instances."""
    return set(
        entry.data.get(CONF_IP_ADDRESS) or entry.data.get(CONF_EMAIL)
        for entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class RainMachineFlowHandler(config_entries.ConfigFlow):
    """Handle a RainMachine config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.local_schema = OrderedDict()
        self.local_schema[vol.Required(CONF_IP_ADDRESS)] = str
        self.local_schema[vol.Required(CONF_PASSWORD)] = str
        self.local_schema[vol.Optional(CONF_PORT, default=DEFAULT_PORT)] = int

        self.remote_schema = OrderedDict()
        self.remote_schema[vol.Required(CONF_EMAIL)] = str
        self.remote_schema[vol.Required(CONF_PASSWORD)] = str

    async def _init_controller(self, connect_type, user_input):
        """Initialize a local or remote controller."""
        websession = aiohttp_client.async_get_clientsession(self.hass)
        client = Client(websession)

        try:
            if connect_type == TYPE_LOCAL:
                await client.load_local(
                    user_input[CONF_IP_ADDRESS],
                    user_input[CONF_PASSWORD],
                    port=user_input[CONF_PORT])
            else:
                await client.load_remote(
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
        except RainMachineError:
            if connect_type == TYPE_LOCAL:
                schema = self.local_schema
            else:
                schema = self.remote_schema

            return self.async_show_form(
                step_id=connect_type,
                data_schema=vol.Schema(schema),
                errors={CONF_EMAIL: 'invalid_credentials'})

        # Since the config entry doesn't allow for configuration of SSL, make
        # sure it's set:
        if user_input.get(CONF_SSL) is None:
            user_input[CONF_SSL] = DEFAULT_SSL

        # Timedeltas are easily serializable, so store the seconds instead:
        scan_interval = user_input.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        user_input[CONF_SCAN_INTERVAL] = scan_interval.seconds

        # Unfortunately, RainMachine doesn't provide a way to refresh the
        # access token without using the IP address and password, so we have to
        # store it:
        return self.async_create_entry(
            title=(
                user_input.get(CONF_IP_ADDRESS) or user_input.get(CONF_EMAIL)),
            data=user_input)

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        # TODO
        # return await self.async_step_user(import_config)

    async def async_step_local(self, user_input=None):
        """Handle the case where the user inputs local credentials."""
        if user_input[CONF_IP_ADDRESS] in configured_instances(self.hass):
            return self.async_show_form(
                step_id=TYPE_LOCAL,
                data_schema=vol.Schema(self.local_schema),
                errors={CONF_IP_ADDRESS: 'identifier_exists'})

        return await self._init_controller(TYPE_LOCAL, user_input)

    async def async_step_remote(self, user_input=None):
        """Handle the case where the user inputs remote credentials."""
        if user_input[CONF_EMAIL] in configured_instances(self.hass):
            return self.async_show_form(
                step_id=TYPE_REMOTE,
                data_schema=vol.Schema(self.remote_schema),
                errors={CONF_EMAIL: 'identifier_exists'})

        return await self._init_controller(TYPE_REMOTE, user_input)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return self.async_show_form(
                step_id='user',
                data_schema=vol.Schema({
                    vol.Required(CONF_TYPE):
                        vol.In([DROPDOWN_LOCAL, DROPDOWN_REMOTE])
                }))

        if user_input[CONF_TYPE] == DROPDOWN_LOCAL:
            return self.async_show_form(
                step_id=TYPE_LOCAL, data_schema=vol.Schema(self.local_schema))

        return self.async_show_form(
            step_id=TYPE_REMOTE, data_schema=vol.Schema(self.remote_schema))
