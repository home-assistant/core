"""Config flow to configure the RainMachine component."""
from regenmaschine import Client
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
from homeassistant.helpers import aiohttp_client

from .const import (  # pylint: disable=unused-import
    CONF_ZONE_RUN_TIME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_ZONE_RUN,
    DOMAIN,
)


class RainMachineFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a RainMachine config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.data_schema = vol.Schema(
            {
                vol.Required(CONF_IP_ADDRESS): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
            }
        )

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=self.data_schema,
            errors=errors if errors else {},
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return await self._show_form()

        await self.async_set_unique_id(user_input[CONF_IP_ADDRESS])
        self._abort_if_unique_id_configured()

        websession = aiohttp_client.async_get_clientsession(self.hass)
        client = Client(session=websession)

        try:
            await client.load_local(
                user_input[CONF_IP_ADDRESS],
                user_input[CONF_PASSWORD],
                port=user_input[CONF_PORT],
                ssl=user_input.get(CONF_SSL, True),
            )
        except RainMachineError:
            return await self._show_form({CONF_PASSWORD: "invalid_credentials"})

        # Unfortunately, RainMachine doesn't provide a way to refresh the
        # access token without using the IP address and password, so we have to
        # store it:
        return self.async_create_entry(
            title=user_input[CONF_IP_ADDRESS],
            data={
                CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_PORT: user_input[CONF_PORT],
                CONF_SSL: user_input.get(CONF_SSL, True),
                CONF_SCAN_INTERVAL: user_input.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL.total_seconds()
                ),
                CONF_ZONE_RUN_TIME: user_input.get(
                    CONF_ZONE_RUN_TIME, DEFAULT_ZONE_RUN
                ),
            },
        )
