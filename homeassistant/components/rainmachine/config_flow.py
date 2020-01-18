"""Config flow to configure the RainMachine component."""

from collections import OrderedDict

from regenmaschine import login
from regenmaschine.errors import RainMachineError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DEFAULT_SSL, DOMAIN


@callback
def configured_instances(hass):
    """Return a set of configured RainMachine instances."""
    return set(
        entry.data[CONF_IP_ADDRESS]
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


@config_entries.HANDLERS.register(DOMAIN)
class RainMachineFlowHandler(config_entries.ConfigFlow):
    """Handle a RainMachine config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.data_schema = OrderedDict()
        self.data_schema[vol.Required(CONF_IP_ADDRESS)] = str
        self.data_schema[vol.Required(CONF_PASSWORD)] = str
        self.data_schema[vol.Optional(CONF_PORT, default=DEFAULT_PORT)] = int

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self.data_schema),
            errors=errors if errors else {},
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""

        if not user_input:
            return await self._show_form()

        if user_input[CONF_IP_ADDRESS] in configured_instances(self.hass):
            return await self._show_form({CONF_IP_ADDRESS: "identifier_exists"})

        websession = aiohttp_client.async_get_clientsession(self.hass)

        try:
            await login(
                user_input[CONF_IP_ADDRESS],
                user_input[CONF_PASSWORD],
                websession,
                port=user_input.get(CONF_PORT, DEFAULT_PORT),
                ssl=True,
            )
        except RainMachineError:
            return await self._show_form({CONF_PASSWORD: "invalid_credentials"})

        # Since the config entry doesn't allow for configuration of SSL, make
        # sure it's set:
        if user_input.get(CONF_SSL) is None:
            user_input[CONF_SSL] = DEFAULT_SSL

        # Timedeltas are easily serializable, so store the seconds instead:
        scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        user_input[CONF_SCAN_INTERVAL] = scan_interval.seconds

        # Unfortunately, RainMachine doesn't provide a way to refresh the
        # access token without using the IP address and password, so we have to
        # store it:
        return self.async_create_entry(
            title=user_input[CONF_IP_ADDRESS], data=user_input
        )
