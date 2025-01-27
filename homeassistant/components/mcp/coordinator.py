"""Types for the Model Context Protocol integration."""

from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
import datetime
import logging

import httpx
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.types import Tool

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = datetime.timedelta(minutes=30)


@asynccontextmanager
async def mcp_client(url: str) -> AsyncGenerator[ClientSession]:
    """Create a server-sent event MCP client.

    This is an asynccontext manager that wraps to other async context managers
    so that the coordinator has a single object to manage.
    """
    try:
        async with sse_client(url=url) as streams, ClientSession(*streams) as session:
            await session.initialize()
            yield session
    except ExceptionGroup as err:
        raise err.exceptions[0] from err


class ModelContextProtocolCoordinator(DataUpdateCoordinator[list[Tool]]):
    """Define an object to hold MCP data."""

    config_entry: ConfigEntry
    session: ClientSession
    ctx_mgr: AbstractAsyncContextManager[ClientSession]

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize ModelContextProtocolCoordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_setup(self) -> None:
        """Set up the client connection."""
        self.ctx_mgr = mcp_client(self.config_entry.data[CONF_URL])
        try:
            self.session = await self.ctx_mgr.__aenter__()  # pylint: disable=unnecessary-dunder-call
        except httpx.HTTPError as err:
            raise UpdateFailed(f"Error communicating with MCP server: {err}") from err

    async def close(self) -> None:
        """Close the client connection."""
        await self.ctx_mgr.__aexit__(None, None, None)

    async def _async_update_data(self) -> list[Tool]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            result = await self.session.list_tools()
        except httpx.HTTPError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        return result.tools
