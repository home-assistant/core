"""Helper functions for the Onkyo component."""
from __future__ import annotations

import asyncio
import contextlib

from pyeiscp import Connection

from homeassistant.core import callback

from .const import DISCOVER_TIMEOUT


async def async_discover_connections(
    timeout: int = DISCOVER_TIMEOUT, host: str | None = None
) -> list[Connection]:
    """Discover all available connections on the network."""
    connections: dict[str, Connection] = {}
    event: asyncio.Event = asyncio.Event()

    @callback
    async def _discovery_callback(connection: Connection) -> None:
        """Handle a discovered connection."""
        if connection.identifier not in connections:
            connections[connection.identifier] = connection
            # We only expect one connection when a host is provided.
            if host and connection.host == host:
                event.set()

    await Connection.discover(
        host=host,
        discovery_callback=_discovery_callback,
        timeout=timeout,
    )

    # Event will be set if host is set and discovered,
    # else discovery runs for the entire timeout time.
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(event.wait(), timeout)

    return list(connections.values())
