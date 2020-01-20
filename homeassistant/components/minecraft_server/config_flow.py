"""Config flow for Minecraft Server integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from . import MinecraftServer
from .const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MinecraftServerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Minecraft Server."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize Minecraft Server config flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            # No configuration data available yet, show default configuration form.
            return await self._show_config_form()

        # User inputs.
        name = user_input[CONF_NAME]
        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]
        update_interval = user_input[CONF_UPDATE_INTERVAL]

        name_exists = False

        # Abort in case the host name was already configured before.
        for config_entry in self.hass.config_entries.async_entries(DOMAIN):
            _LOGGER.debug(
                "Config entry: name=%s, host=%s",
                config_entry.data[CONF_NAME],
                config_entry.data[CONF_HOST],
            )
            if config_entry.data[CONF_HOST] == host:
                # Abort if a config entry exists with same host name.
                return self.async_abort(reason="host_exists")
            if config_entry.data[CONF_NAME] == name:
                # Name already exists.
                name_exists = True

        errors = {}

        # Validate name configuration (no duplicate).
        if name_exists:
            errors["base"] = "name_exists"
        # Validate port configuration (limit to user and dynamic port range).
        elif (port < 1024) or (port > 65535):
            errors["base"] = "invalid_port"
        # Validate update interval configuration (min: 5s, max: 24h).
        elif (update_interval < 5) or (update_interval > 86400):
            errors["base"] = "invalid_update_interval"
        # Validate host and port via ping request to server.
        else:
            server = MinecraftServer(self.hass, name=name, host=host, port=port,)
            await server.async_check_connection()
            if not server.online():
                errors["base"] = "cannot_connect"
            del server

        # Configuration data are available, but an error was detected.
        # Show configuration form with error message.
        if "base" in errors:
            _LOGGER.error("Error occured during config flow: %s", errors["base"])
            return await self._show_config_form(user_input, errors=errors,)

        # Configuration data are available and no error was detected, create configuration entry.
        return self.async_create_entry(title=name, data=user_input)

    async def _show_config_form(
        self, user_input=None, errors=None,
    ):
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
                    ): str,
                    vol.Optional(
                        CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=user_input.get(
                            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS
                        ),
                    ): int,
                }
            ),
            errors=errors,
        )
