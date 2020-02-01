"""Config flow for Minecraft Server integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL

from . import MinecraftServer
from .const import (  # pylint: disable=unused-import
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


class MinecraftServerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Minecraft Server."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            # No configuration data available yet, show default configuration form.
            return await self._show_config_form()

        # User inputs.
        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]
        scan_interval = user_input[CONF_SCAN_INTERVAL]

        # Abort in case the host was already configured before.
        unique_id = f"{host.lower()}-{port}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        errors = {}

        # Validate port configuration (limit to user and dynamic port range).
        if (port < 1024) or (port > 65535):
            errors["base"] = "invalid_port"
        # Validate scan interval configuration (min: 5s, max: 24h).
        elif (scan_interval < 5) or (scan_interval > 86400):
            errors["base"] = "invalid_scan_interval"
        # Validate host and port via ping request to server.
        else:
            server = MinecraftServer(self.hass, unique_id, user_input)
            await server.async_check_connection()
            if not server.online:
                errors["base"] = "cannot_connect"
            del server

        # Configuration data are available, but an error was detected.
        # Show configuration form with error message.
        if "base" in errors:
            return await self._show_config_form(user_input, errors=errors)

        # Configuration data are available and no error was detected, create configuration entry.
        return self.async_create_entry(title=f"{host.lower()}:{port}", data=user_input)

    async def _show_config_form(self, user_input=None, errors=None):
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
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                    vol.Optional(
                        CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): int,
                }
            ),
            errors=errors,
        )
