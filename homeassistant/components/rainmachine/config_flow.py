"""Config flow to configure the RainMachine component."""
from regenmaschine import Client
from regenmaschine.errors import RainMachineError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_SSL
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import (  # pylint: disable=unused-import
    CONF_ZONE_RUN_TIME,
    DEFAULT_PORT,
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Define the config flow to handle options."""
        return RainMachineOptionsFlowHandler(config_entry)

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
            return await self._show_form({CONF_PASSWORD: "invalid_auth"})

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
                CONF_ZONE_RUN_TIME: user_input.get(
                    CONF_ZONE_RUN_TIME, DEFAULT_ZONE_RUN
                ),
            },
        )


class RainMachineOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a RainMachine options flow."""

    def __init__(self, config_entry):
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ZONE_RUN_TIME,
                        default=self.config_entry.options.get(CONF_ZONE_RUN_TIME),
                    ): cv.positive_int
                }
            ),
        )
