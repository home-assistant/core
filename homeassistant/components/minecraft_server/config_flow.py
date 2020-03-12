"""Config flow for Minecraft Server integration."""
from functools import partial
import ipaddress

import getmac
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from . import MinecraftServer
from .const import (  # pylint: disable=unused-import
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
)


class MinecraftServerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Minecraft Server."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # User inputs.
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            unique_id = ""

            # Check if 'host' is a valid IP address and if so, get the MAC address.
            ip_address = None
            mac_address = None
            try:
                ip_address = ipaddress.ip_address(host)
            except ValueError:
                # Host is not a valid IP address.
                pass
            else:
                # Host is a valid IP address.
                if ip_address.version == 4:
                    # Address type is IPv4.
                    params = {"ip": host}
                else:
                    # Address type is IPv6.
                    params = {"ip6": host}
                mac_address = await self.hass.async_add_executor_job(
                    partial(getmac.get_mac_address, **params)
                )

            # Validate IP address via valid MAC address.
            if ip_address is not None and mac_address is None:
                errors["base"] = "invalid_ip"
            # Validate port configuration (limit to user and dynamic port range).
            elif (port < 1024) or (port > 65535):
                errors["base"] = "invalid_port"
            # Validate host and port via ping request to server.
            else:
                # Build unique_id.
                if ip_address is not None:
                    # Since IP addresses can change and therefore are not allowed in a
                    # unique_id, fall back to the MAC address.
                    unique_id = f"{mac_address}-{port}"
                else:
                    # Use host name in unique_id (host names should not change).
                    unique_id = f"{host}-{port}"

                # Abort in case the host was already configured before.
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                # Create server instance with configuration data and try pinging the server.
                server = MinecraftServer(self.hass, unique_id, user_input)
                await server.async_check_connection()
                if not server.online:
                    # Host or port invalid or server not reachable.
                    errors["base"] = "cannot_connect"
                else:
                    # Configuration data are available and no error was detected, create configuration entry.
                    return self.async_create_entry(
                        title=f"{host}:{port}", data=user_input
                    )

        # Show configuration form (default form in case of no user_input,
        # form filled with user_input and eventually with errors otherwise).
        return self._show_config_form(user_input, errors)

    def _show_config_form(self, user_input=None, errors=None):
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
                    vol.Optional(
                        CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                }
            ),
            errors=errors,
        )
