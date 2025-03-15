"""Types for the Model Context Protocol integration."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import datetime
import logging

import httpx
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
import voluptuous as vol
from voluptuous_openapi import convert_to_voluptuous

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.json import JsonObjectType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = datetime.timedelta(minutes=30)
TIMEOUT = 10


@asynccontextmanager
async def mcp_client(url: str) -> AsyncGenerator[ClientSession]:
    """Create a server-sent event MCP client.

    This is an asynccontext manager that exists to wrap other async context managers
    so that the coordinator has a single object to manage.
    """
    try:
        async with sse_client(url=url, sse_read_timeout=None) as streams, ClientSession(*streams) as session:
            await session.initialize()
            yield session
    except ExceptionGroup as err:
        raise err.exceptions[0] from err


class ModelContextProtocolTool(llm.Tool):
    """A Tool exposed over the Model Context Protocol."""

    def __init__(
        self,
        name: str,
        description: str | None,
        parameters: vol.Schema,
        session: ClientSession,
    ) -> None:
        """Initialize the tool."""
        self.name = name
        self.description = description
        self.parameters = parameters
        self.session = session

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Call the tool."""
        try:
            result = await self.session.call_tool(
                tool_input.tool_name, tool_input.tool_args
            )
        except httpx.HTTPStatusError as error:
            raise HomeAssistantError(f"Error when calling tool: {error}") from error
        return result.model_dump(exclude_unset=True, exclude_none=True)


class ModelContextProtocolCoordinator(DataUpdateCoordinator[list[llm.Tool]]):
    """Define an object to hold MCP data."""

    config_entry: ConfigEntry
    _session: ClientSession | None = None
    _setup_error: Exception | None = None

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize ModelContextProtocolCoordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=UPDATE_INTERVAL,
        )
        self._stop = asyncio.Event()

    async def _async_setup(self) -> None:
        """Set up the client connection."""
        connected = asyncio.Event()
        stop = asyncio.Event()
        self.config_entry.async_create_background_task(
            self.hass, self._connect(connected, stop), "mcp-client"
        )
        try:
            async with asyncio.timeout(TIMEOUT):
                await connected.wait()
                self._stop = stop
        finally:
            if self._setup_error is not None:
                raise self._setup_error

    async def _connect(self, connected: asyncio.Event, stop: asyncio.Event) -> None:
        """Create a server-sent event MCP client."""
        url = self.config_entry.data[CONF_URL]
        try:
            async with (
                sse_client(url=url, sse_read_timeout=None) as streams,
                ClientSession(*streams) as session,
            ):
                await session.initialize()
                self._session = session
                connected.set()
                await stop.wait()
        except httpx.HTTPStatusError as err:
            self._setup_error = err
            _LOGGER.debug("Error connecting to MCP server: %s", err)
            raise UpdateFailed(f"Error connecting to MCP server: {err}") from err
        except ExceptionGroup as err:
            self._setup_error = err.exceptions[0]
            _LOGGER.debug("Error connecting to MCP server: %s", err)
            raise UpdateFailed(
                "Error connecting to MCP server: {err.exceptions[0]}"
            ) from err.exceptions[0]
        finally:
            self._session = None

    async def close(self) -> None:
        """Close the client connection."""
        if self._stop is not None:
            self._stop.set()

    async def _async_update_data(self) -> list[llm.Tool]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        if self._session is None:
            raise UpdateFailed("No session available")
        try:
            result = await self._session.list_tools()
        except httpx.HTTPError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        _LOGGER.debug("Received tools: %s", result.tools)
        tools: list[llm.Tool] = []
        for tool in result.tools:
            try:
                parameters = convert_to_voluptuous(tool.inputSchema)
            except Exception as err:
                raise UpdateFailed(
                    f"Error converting schema {err}: {tool.inputSchema}"
                ) from err
            tools.append(
                ModelContextProtocolTool(
                    tool.name,
                    tool.description,
                    parameters,
                    self._session,
                )
            )
        return tools
