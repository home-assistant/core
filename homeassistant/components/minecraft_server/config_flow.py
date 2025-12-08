"""Config flow for Minecraft Server integration."""

from __future__ import annotations

from collections.abc import Coroutine
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_TYPE
from homeassistant.helpers.selector import selector

from .api import MinecraftServer, MinecraftServerAddressError, MinecraftServerType
from .const import DOMAIN
from .server_locator import LocalServerLocator

DEFAULT_ADDRESS = "localhost:25565"

_LOGGER = logging.getLogger(__name__)

SERVER_LOCATOR = LocalServerLocator()

NO_SERVERS_FOUND_MESSAGE = (
    "No local Minecraft servers found. Please enter the server address manually."
)


class MinecraftServerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for the Minecraft Server integration.

    Adds suggested servers discovered on the local network.
    """

    VERSION = 3

    SUGGESTED_SERVERS: list[str] = []
    SUGGESTED_SERVERS_DATA: list[Any] = []

    in_progress_suggested_servers: Coroutine[None, Any, list[str]]
    in_progress_suggested_server_data: Any

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        self.in_progress_suggested_servers = SERVER_LOCATOR.find_servers()

        errors: dict[str, str] = {}

        if user_input:
            address = user_input[CONF_ADDRESS]

            # Abort config flow if service is already configured.
            self._async_abort_entries_match({CONF_ADDRESS: address})

            # Prepare config entry data.
            config_data = {
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
        return await self._show_config_form(user_input, errors)

    async def _show_config_form(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Show the setup form to the user."""
        if user_input is None:
            user_input = {}

        schema_entries: dict[vol.Marker, Any] = {}

        self.SUGGESTED_SERVERS = await self.in_progress_suggested_servers

        if len(self.SUGGESTED_SERVERS) <= 0:
            self.SUGGESTED_SERVERS.append(NO_SERVERS_FOUND_MESSAGE)

        else:
            self.in_progress_suggested_server_data = [
                MinecraftServer(
                    server_type=MinecraftServerType.JAVA_EDITION,
                    address=server,
                    hass=self.hass,
                )
                for server in self.SUGGESTED_SERVERS
            ]
            for server in self.in_progress_suggested_server_data:
                await server.async_initialize()

            self.in_progress_suggested_server_data = [
                await server.async_get_data()
                for server in self.in_progress_suggested_server_data
            ]

            self.SUGGESTED_SERVERS_DATA = [
                {"value": address, "label": f"{data.motd} | {address}"}
                for (data, address) in zip(
                    self.in_progress_suggested_server_data,
                    self.SUGGESTED_SERVERS,
                    strict=True,
                )
            ]

        schema_entries[
            vol.Required(
                CONF_ADDRESS,
                default=user_input.get(CONF_ADDRESS, DEFAULT_ADDRESS),
            )
        ] = selector(
            {
                "select": {
                    "options": (
                        self.SUGGESTED_SERVERS_DATA
                        if len(self.SUGGESTED_SERVERS_DATA) >= 0
                        else self.SUGGESTED_SERVERS
                    ),
                    "custom_value": True,
                }
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema_entries),
            errors=errors,
        )
