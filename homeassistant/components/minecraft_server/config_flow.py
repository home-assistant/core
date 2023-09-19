"""Config flow for Minecraft Server integration."""
from contextlib import suppress
import logging

from mcstatus import JavaServer
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from . import helpers
from .const import DEFAULT_HOST, DEFAULT_NAME, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MinecraftServerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Minecraft Server."""

    VERSION = 2

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            host = None
            port = DEFAULT_PORT
            title = user_input[CONF_HOST]

            # Split address at last occurrence of ':'.
            address_left, separator, address_right = user_input[CONF_HOST].rpartition(
                ":"
            )

            # If no separator is found, 'rpartition' returns ('', '', original_string).
            if separator == "":
                host = address_right
            else:
                host = address_left
                with suppress(ValueError):
                    port = int(address_right)

            # Remove '[' and ']' in case of an IPv6 address.
            host = host.strip("[]")

            # Validate port configuration (limit to user and dynamic port range).
            if (port < 1024) or (port > 65535):
                errors["base"] = "invalid_port"
            # Validate host and port by checking the server connection.
            else:
                # Create server instance with configuration data and ping the server.
                config_data = {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_HOST: host,
                    CONF_PORT: port,
                }
                if await self._async_is_server_online(host, port):
                    # Configuration data are available and no error was detected,
                    # create configuration entry.
                    return self.async_create_entry(title=title, data=config_data)

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
                        CONF_HOST, default=user_input.get(CONF_HOST, DEFAULT_HOST)
                    ): vol.All(str, vol.Lower),
                }
            ),
            errors=errors,
        )

    async def _async_is_server_online(self, host: str, port: int) -> bool:
        """Check server connection using a 'status' request and return result."""

        # Check if host is a SRV record. If so, update server data.
        if srv_record := await helpers.async_check_srv_record(host):
            # Use extracted host and port from SRV record.
            host = srv_record[CONF_HOST]
            port = srv_record[CONF_PORT]

        # Send a status request to the server.
        server = JavaServer(host, port)
        try:
            await server.async_status()
            return True
        except OSError as error:
            _LOGGER.debug(
                (
                    "Error occurred while trying to check the connection to '%s:%s' -"
                    " OSError: %s"
                ),
                host,
                port,
                error,
            )

        return False
