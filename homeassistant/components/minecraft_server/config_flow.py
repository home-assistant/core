"""Config flow for Minecraft Server integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from . import MinecraftServer
from .const import (  # pylint:disable=unused-import
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

    async def async_step_user(self, user_input):
        """Handle the initial step."""
        if user_input is None:
            # No configuration data available yet, show default configuration form.
            return await self._show_config_form()

        name_exists = False

        # Abort in case the host name was already configured before.
        for config_entry in self.hass.config_entries.async_entries(DOMAIN):
            _LOGGER.debug(
                "Config entry: name=%s, host=%s",
                config_entry.data[CONF_NAME],
                config_entry.data[CONF_HOST],
            )
            if config_entry.data[CONF_HOST] == user_input[CONF_HOST]:
                # Abort if a config entry exists with same host name.
                return self.async_abort(reason="host_exists")
            if config_entry.data[CONF_NAME] == user_input[CONF_NAME]:
                # Name already exists.
                name_exists = True

        errors = {}

        # Validate name configuration (no duplicate).
        if name_exists:
            errors["base"] = "name_exists"
        # Validate port configuration (limit to user and dynamic port range).
        elif (user_input[CONF_PORT] < 1024) or (user_input[CONF_PORT] > 65535):
            errors["base"] = "invalid_port"
        # Validate update interval configuration (min: 5s, max: 24h).
        elif (user_input[CONF_UPDATE_INTERVAL] < 5) or (
            user_input[CONF_UPDATE_INTERVAL] > 84600
        ):
            errors["base"] = "invalid_update_interval"
        # Validate host and port via ping request to server.
        else:
            server = MinecraftServer(
                self.hass,
                name=user_input[CONF_NAME],
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
            )
            await server.async_check_connection()
            if not server.online():
                errors["base"] = "cannot_connect"
            del server

        # Configuration data are available, but an error was detected.
        # Show configuration form with error message.
        if "base" in errors:
            _LOGGER.error("Error occured during config flow: %s", errors["base"])
            return await self._show_config_form(
                default_name=user_input[CONF_NAME],
                default_host=user_input[CONF_HOST],
                default_port=user_input[CONF_PORT],
                default_update_interval=user_input[CONF_UPDATE_INTERVAL],
                errors=errors,
            )

        # Configuration data are available and no error was detected, create configuration entry.
        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

    async def _show_config_form(
        self,
        default_name=DEFAULT_NAME,
        default_host=DEFAULT_HOST,
        default_port=DEFAULT_PORT,
        default_update_interval=DEFAULT_UPDATE_INTERVAL_SECONDS,
        errors=None,
    ):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=default_name): str,
                    vol.Required(CONF_HOST, default=default_host): str,
                    vol.Optional(CONF_PORT, default=default_port): int,
                    vol.Required(
                        CONF_UPDATE_INTERVAL, default=default_update_interval
                    ): int,
                }
            ),
            errors=errors,
        )
