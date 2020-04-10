"""Config flow for Minecraft Server integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from . import MinecraftServer, helpers
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
            host = None
            port = DEFAULT_PORT
            # Split address at last occurrence of ':'.
            address_left, separator, address_right = user_input[CONF_HOST].rpartition(
                ":"
            )
            # If no separator is found, 'rpartition' return ('', '', original_string).
            if separator == "":
                host = address_right
            else:
                host = address_left
                try:
                    port = int(address_right)
                except ValueError:
                    pass  # 'port' is already set to default value.

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
                server = MinecraftServer(self.hass, "dummy_unique_id", config_data)
                await server.async_check_connection()
                if not server.online:
                    # Host or port invalid or server not reachable.
                    errors["base"] = "cannot_connect"
                else:
                    # Build unique_id and config entry title.
                    unique_id = ""
                    title = f"{host}:{port}"
                    # Check if 'host' is a valid SRV record.
                    srv_record = await helpers.async_check_srv_record(self.hass, host)
                    if srv_record is not None:
                        # Use only SRV host name in unique_id (does not change).
                        unique_id = f"{host}-srv"
                        title = host
                    else:
                        # Use host name and port in unique_id (to support servers with
                        # same host name but different ports).
                        unique_id = f"{host}-{port}"

                    # Abort in case the host was already configured before.
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    # Configuration data are available and no error was detected, create configuration entry.
                    return self.async_create_entry(title=title, data=config_data)

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
                }
            ),
            errors=errors,
        )
