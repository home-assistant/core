"""Config flow for Onkyo."""
from __future__ import annotations

import asyncio
from typing import Any

import async_timeout
from pyeiscp import Connection
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_ENABLED_SOURCES,
    CONF_IDENTIFIER,
    CONF_MAX_VOLUME,
    CONF_SOURCES,
    CONNECT_TIMEOUT,
    DEFAULT_MAX_VOLUME,
    DEFAULT_SOURCE_NAMES,
    DEFAULT_SOURCES,
    DISCOVER_TIMEOUT,
)
from .const import DOMAIN  # pylint:disable=unused-import


class OnkyoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Onkyo component."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discovered_connections: list[Connection] = []
        self._connection: Connection | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if not self._discovered_connections:
            # Discover connections and filter out already configured entries.
            self._discovered_connections = [
                conn
                for conn in await _discover_connections(DISCOVER_TIMEOUT)
                if conn.identifier
                not in [
                    entity.unique_id
                    for entity in self._async_current_entries(include_ignore=True)
                ]
            ]

        if len(self._discovered_connections) == 1:
            # One connection discovered, immediately connect.
            self._connection = self._discovered_connections[0]
            return await self.async_step_connect()
        if len(self._discovered_connections) > 1:
            # Multiple connections discovered, let user select.
            return await self.async_step_select()

        errors["base"] = "discovery_error"

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({}), errors=errors
        )

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle multiple network receivers found."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Get selected connection and go to the connect step.
            self._connection = next(
                conn
                for conn in self._discovered_connections
                if conn.name == user_input["select_receiver"]
            )
            return await self.async_step_connect()

        select_scheme = vol.Schema(
            {
                vol.Required("select_receiver"): vol.In(
                    [conn.name for conn in self._discovered_connections]
                )
            }
        )

        return self.async_show_form(
            step_id="select", data_schema=select_scheme, errors=errors
        )

    async def async_step_connect(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Connect to the network receiver."""
        if self._connection:
            await self.async_set_unique_id(self._connection.identifier)
            self._abort_if_unique_id_configured()

            try:
                with async_timeout.timeout(CONNECT_TIMEOUT):
                    await self._connection.connect()

            except asyncio.TimeoutError:
                return self.async_abort(reason="cannot_connect")

            # Close the test connection as setup entry will create one.
            self._connection.close()
            return self.async_create_entry(
                title=self._connection.name,
                data={
                    CONF_IDENTIFIER: self._connection.identifier,
                    CONF_HOST: self._connection.host,
                    CONF_NAME: self._connection.name,
                },
            )

        return self.async_abort(reason="unknown")


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for the Onkyo component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry: config_entries.ConfigEntry = config_entry
        self._options: dict[str, str | dict[str, Any]] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow initialized by the user."""
        # Create a dictionary with all sources and set custom source names.
        sources = (
            {**DEFAULT_SOURCE_NAMES, **self.config_entry.options[CONF_SOURCES]}
            if CONF_SOURCES in self.config_entry.options
            else {**DEFAULT_SOURCE_NAMES, **DEFAULT_SOURCES}
        )

        if user_input is not None:
            # Store the input to update the entry after the next step.
            self._options = {
                CONF_MAX_VOLUME: user_input[CONF_MAX_VOLUME],
                CONF_SOURCES: {
                    key: source_name
                    for key, source_name in sources.items()
                    if key in user_input[CONF_ENABLED_SOURCES]
                },
            }
            return await self.async_step_source_names()

        settings_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_MAX_VOLUME,
                    default=self.config_entry.options.get(
                        CONF_MAX_VOLUME, DEFAULT_MAX_VOLUME
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    CONF_ENABLED_SOURCES,
                    default=list(
                        self.config_entry.options.get(
                            CONF_SOURCES, DEFAULT_SOURCES
                        ).keys()
                    ),
                ): cv.multi_select(
                    {
                        key: f"{source_name} ({key})"
                        for key, source_name in sources.items()
                    }
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=settings_schema)

    async def async_step_source_names(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Options to change the default source names."""
        if user_input is not None:
            self._options[CONF_SOURCES] = user_input
            return self.async_create_entry(title="", data=self._options)

        sources = self._options[CONF_SOURCES]
        if isinstance(sources, dict):
            source_names_schema = vol.Schema(
                {
                    vol.Optional(
                        key,
                        default=source_name,
                    ): str
                    for key, source_name in sources.items()
                }
            )

            return self.async_show_form(
                step_id="source_names", data_schema=source_names_schema
            )

        return self.async_abort(reason="unknown")


async def _discover_connections(timeout: int) -> list[Connection]:
    """Discover available connections on the network."""
    connections: dict[str, Connection] = {}

    @callback
    async def _discovery_callback(connection: Connection) -> None:
        """Handle a discovered connection."""
        if connection.identifier not in connections:
            connections[connection.identifier] = connection

    await Connection.discover(
        discovery_callback=_discovery_callback,
        timeout=timeout,
    )

    await asyncio.sleep(timeout)
    return list(connections.values())
