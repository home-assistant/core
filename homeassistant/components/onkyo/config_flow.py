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
    DEFAULT_SOURCE_NAMES,
    DEFAULT_SOURCES,
    DOMAIN,
)
from .helpers import async_discover_connections

MANUAL_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


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

    async def async_step_import(self, import_info: dict[str, Any]) -> FlowResult:
        """Handle a flow initialized by importing a config."""
        connection = next(
            iter(
                self.get_unique_connections(
                    await async_discover_connections(host=import_info[CONF_HOST])
                )
            ),
            None,
        )

        if connection and await _validate_connection(connection):
            await self.async_set_unique_id(connection.identifier)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=import_info[CONF_NAME],
                data={
                    CONF_IDENTIFIER: connection.identifier,
                    CONF_HOST: connection.host,
                    CONF_NAME: import_info[CONF_NAME],
                    CONF_MAX_VOLUME: import_info[CONF_MAX_VOLUME],
                },
                options={
                    CONF_SOURCES: import_info[CONF_SOURCES],
                },
            )

        return self.async_abort(reason="unknown")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if not self._discovered_connections:
            self._discovered_connections = self.get_unique_connections(
                await async_discover_connections()
            )

        if len(self._discovered_connections) == 0:
            # No connections discovered, switch to manual host input.
            return await self.async_step_manual()

        if len(self._discovered_connections) == 1:
            # One connection discovered, immediately connect.
            self._connection = self._discovered_connections[0]
            return await self.async_step_connect()

        # Multiple connections discovered, let user select.
        return await self.async_step_select()

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Discover a receiver using a manually set host."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Run discovery for specified host.
            self._connection = next(
                iter(
                    self.get_unique_connections(
                        await async_discover_connections(host=user_input[CONF_HOST])
                    )
                ),
                None,
            )

            if self._connection:
                return await self.async_step_connect()

            errors["base"] = "discovery_error"

        return self.async_show_form(
            step_id="manual", data_schema=MANUAL_SCHEMA, errors=errors
        )

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle multiple network receivers found."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Get selected connection and go to the connect step.
            self._connection = next(
                (
                    conn
                    for conn in self._discovered_connections
                    if conn.name == user_input["select_receiver"]
                ),
                None,
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
        conn: Connection = self._connection
        await self.async_set_unique_id(conn.identifier)
        self._abort_if_unique_id_configured()

        if not await _validate_connection(conn):
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=conn.name,
            data={
                CONF_IDENTIFIER: conn.identifier,
                CONF_HOST: conn.host,
                CONF_NAME: conn.name,
            },
        )

    def get_unique_connections(self, connections: list[Connection]) -> list[Connection]:
        """Filter out connections that are already set up."""
        return [
            conn
            for conn in connections
            if conn.identifier
            not in [
                entity.unique_id
                for entity in self._async_current_entries(include_ignore=True)
            ]
        ]


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

        source_names_schema = vol.Schema(
            {
                vol.Optional(
                    key,
                    default=source_name,
                ): str
                for key, source_name in self._options[CONF_SOURCES].items()  # type: ignore[union-attr]
            }
        )

        return self.async_show_form(
            step_id="source_names", data_schema=source_names_schema
        )


async def _validate_connection(connection: Connection) -> bool:
    """Validate if we can connect to a connection."""
    try:
        with async_timeout.timeout(CONNECT_TIMEOUT):
            await connection.connect()

    except asyncio.TimeoutError:
        return False

    connection.close()
    return True
