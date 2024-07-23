"""Config flow for Minecraft Server integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_TYPE

from .api import MinecraftServer, MinecraftServerAddressError, MinecraftServerType
from .const import DEFAULT_NAME, DOMAIN

DEFAULT_ADDRESS = "localhost:25565"

_LOGGER = logging.getLogger(__name__)


class MinecraftServerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Minecraft Server."""

    VERSION = 3

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input:
            address = user_input[CONF_ADDRESS]

            # Abort config flow if service is already configured.
            self._async_abort_entries_match({CONF_ADDRESS: address})

            # Prepare config entry data.
            config_data = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_ADDRESS: address,
            }

            # Some Bedrock Edition servers mimic a Java Edition server, therefore check for a Bedrock Edition server first.
            for server_type in MinecraftServerType:
                api = MinecraftServer(self.hass, server_type, address)

                try:
                    await api.async_initialize()
                except MinecraftServerAddressError as error:
                    _LOGGER.debug(
                        "Initialization of %s server failed: %s",
                        server_type,
                        error,
                    )
                else:
                    if await api.async_is_online():
                        config_data[CONF_TYPE] = server_type
                        return self.async_create_entry(title=address, data=config_data)

            # Host or port invalid or server not reachable.
            errors["base"] = "cannot_connect"

        # Show configuration form (default form in case of no user_input,
        # form filled with user_input and eventually with errors otherwise).
        return self._show_config_form(user_input, errors)

    def _show_config_form(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
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
