"""Coordinator and helpers for the Model Context Protocol integration."""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
import datetime
import logging
from typing import cast

import httpx
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
import voluptuous as vol
from voluptuous_openapi import convert_to_voluptuous

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.json import JsonObjectType

from .const import CONF_TRANSPORT, DOMAIN, TRANSPORT_SSE, TRANSPORT_STREAMABLE_HTTP

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = datetime.timedelta(minutes=30)
TIMEOUT = 10

type TokenManager = Callable[[], Awaitable[str]]


@asynccontextmanager
async def mcp_client(
    url: str,
    token_manager: TokenManager | None = None,
    *,
    transport: str = TRANSPORT_SSE,
) -> AsyncGenerator[ClientSession]:
    """Create an MCP client using the configured transport."""

    headers: dict[str, str] = {}
    if token_manager is not None:
        token = await token_manager()
        headers["Authorization"] = f"Bearer {token}"
    try:
        if transport == TRANSPORT_STREAMABLE_HTTP:
            async with (
                streamablehttp_client(
                    url=url,
                    headers=headers,
                    timeout=TIMEOUT,
                ) as (read_stream, write_stream, _),
                ClientSession(read_stream, write_stream) as session,
            ):
                await session.initialize()
                yield session
        else:
            async with (
                sse_client(url=url, headers=headers, timeout=TIMEOUT) as streams,
                ClientSession(*streams) as session,
            ):
                await session.initialize()
                yield session
    except ExceptionGroup as err:
        _LOGGER.debug("Error creating MCP client: %s", err)
        raise err.exceptions[0] from err


class ModelContextProtocolTool(llm.Tool):
    """A Tool exposed over the Model Context Protocol."""

    def __init__(
        self,
        name: str,
        description: str | None,
        parameters: vol.Schema,
        server_url: str,
        token_manager: TokenManager | None = None,
        *,
        transport: str = TRANSPORT_SSE,
    ) -> None:
        """Initialize the tool."""
        self.name = name
        self.description = description
        self.parameters = parameters
        self.server_url = server_url
        self.token_manager = token_manager
        self.transport = transport

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Call the tool."""
        try:
            async with asyncio.timeout(TIMEOUT):
                async with mcp_client(
                    self.server_url, self.token_manager, transport=self.transport
                ) as session:
                    result = await session.call_tool(
                        tool_input.tool_name, tool_input.tool_args
                    )
        except TimeoutError as error:
            _LOGGER.debug("Timeout when calling tool: %s", error)
            raise HomeAssistantError(f"Timeout when calling tool: {error}") from error
        except httpx.HTTPStatusError as error:
            _LOGGER.debug("Error when calling tool: %s", error)
            raise HomeAssistantError(f"Error when calling tool: {error}") from error
        return cast(
            JsonObjectType, result.model_dump(exclude_unset=True, exclude_none=True)
        )


class ModelContextProtocolCoordinator(DataUpdateCoordinator[list[llm.Tool]]):
    """Define an object to hold MCP data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        token_manager: TokenManager | None = None,
    ) -> None:
        """Initialize ModelContextProtocolCoordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=UPDATE_INTERVAL,
        )
        self.token_manager = token_manager
        self.transport: str = cast(
            str, config_entry.data.get(CONF_TRANSPORT, TRANSPORT_SSE)
        )
        if self.transport not in (TRANSPORT_SSE, TRANSPORT_STREAMABLE_HTTP):
            self.transport = TRANSPORT_SSE

    async def _async_update_data(self) -> list[llm.Tool]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            async with asyncio.timeout(TIMEOUT):
                async with mcp_client(
                    self.config_entry.data[CONF_URL],
                    self.token_manager,
                    transport=self.transport,
                ) as session:
                    result = await session.list_tools()
        except TimeoutError as error:
            _LOGGER.debug("Timeout when listing tools: %s", error)
            raise UpdateFailed(f"Timeout when listing tools: {error}") from error
        except httpx.HTTPStatusError as error:
            _LOGGER.debug("Error communicating with API: %s", error)
            if error.response.status_code == 401 and self.token_manager is not None:
                raise ConfigEntryAuthFailed(
                    "The MCP server requires authentication"
                ) from error
            raise UpdateFailed(f"Error communicating with API: {error}") from error
        except httpx.HTTPError as err:
            _LOGGER.debug("Error communicating with API: %s", err)
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
                    self.config_entry.data[CONF_URL],
                    self.token_manager,
                    transport=self.transport,
                )
            )
        return tools
