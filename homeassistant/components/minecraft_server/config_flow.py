"""Config flow for Minecraft Server integration."""
import logging

from mcstatus import JavaServer
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DOMAIN

DEFAULT_ADDRESS = "localhost:25565"

_LOGGER = logging.getLogger(__name__)


class MinecraftServerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Minecraft Server."""

    VERSION = 3

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input:
            address = user_input[CONF_ADDRESS]

            if await self._async_is_server_online(address):
                # No error was detected, create configuration entry.
                config_data = {CONF_NAME: user_input[CONF_NAME], CONF_ADDRESS: address}
                return self.async_create_entry(title=address, data=config_data)

            # Host or port invalid or server not reachable.
            errors["base"] = "cannot_connect"

        # Show configuration form (default form in case of no user_input,
        # form filled with user_input and eventually with errors otherwise).
        return self._show_config_form(user_input, errors)

    def _show_config_form(self, user_input=None, errors=None) -> FlowResult:
        """Show the setup form to the user."""
        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                    vol.Required(
                        CONF_ADDRESS,
                        default=user_input.get(CONF_ADDRESS, DEFAULT_ADDRESS),
                    ): vol.All(str, vol.Lower),
                }
            ),
            errors=errors,
        )

    async def _async_is_server_online(self, address: str) -> bool:
        """Check server connection using a 'status' request and return result."""

        # Parse and check server address.
        try:
            server = await JavaServer.async_lookup(address)
        except ValueError as error:
            _LOGGER.debug(
                (
                    "Error occurred while parsing server address '%s' -"
                    " ValueError: %s"
                ),
                address,
                error,
            )
            return False

        # Send a status request to the server.
        try:
            await server.async_status()
            return True
        except OSError as error:
            _LOGGER.debug(
                (
                    "Error occurred while trying to check the connection to '%s:%s' -"
                    " OSError: %s"
                ),
                server.address.host,
                server.address.port,
                error,
            )

        return False
