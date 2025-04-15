"""Types for the Model Context Protocol integration."""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
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
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.json import JsonObjectType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = datetime.timedelta(minutes=30)
TIMEOUT = 10

TokenManager = Callable[[], Awaitable[str]]


@asynccontextmanager
async def mcp_client(
    url: str,
    token_manager: TokenManager | None = None,
) -> AsyncGenerator[ClientSession]:
    """Create a server-sent event MCP client.

    This is an asynccontext manager that exists to wrap other async context managers
    so that the coordinator has a single object to manage.
    """
    headers: dict[str, str] = {}
    if token_manager is not None:
        token = await token_manager()
        headers["Authorization"] = f"Bearer {token}"
    try:
        async with (
            sse_client(url=url, headers=headers) as streams,
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
    ) -> None:
        """Initialize the tool."""
        self.name = name
        self.description = description
        self.parameters = parameters
        self.server_url = server_url
        self.token_manager = token_manager

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Call the tool."""
        try:
            async with asyncio.timeout(TIMEOUT):
                async with mcp_client(self.server_url, self.token_manager) as session:
                    result = await session.call_tool(
                        tool_input.tool_name, tool_input.tool_args
                    )
        except TimeoutError as error:
            _LOGGER.debug("Timeout when calling tool: %s", error)
            raise HomeAssistantError(f"Timeout when calling tool: {error}") from error
        except httpx.HTTPStatusError as error:
            _LOGGER.debug("Error when calling tool: %s", error)
            raise HomeAssistantError(f"Error when calling tool: {error}") from error
        return result.model_dump(exclude_unset=True, exclude_none=True)


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

    async def _async_update_data(self) -> list[llm.Tool]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            async with asyncio.timeout(TIMEOUT):
                async with mcp_client(
                    self.config_entry.data[CONF_URL], self.token_manager
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
                )
            )
        return tools
