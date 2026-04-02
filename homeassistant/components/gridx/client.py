"""Client helpers for the GridX integration."""

from __future__ import annotations

from importlib import import_module
from typing import Any, Protocol

import httpx


class GridxConnector(Protocol):
    """Protocol for the GridX connector used by the integration."""

    async def retrieve_live_data(self) -> list[dict[str, Any]]:
        """Retrieve live data for all systems."""

    async def retrieve_historical_data(
        self,
        *,
        start: str,
        end: str,
        resolution: str,
    ) -> list[dict[str, Any]]:
        """Retrieve historical data for all systems."""

    async def close(self) -> None:
        """Close the connector and any owned clients."""


async def async_create_connector(
    config: dict[str, Any],
    httpx_client: httpx.AsyncClient,
) -> GridxConnector:
    """Create a GridX connector without importing the dependency at module import time."""
    connector_module = import_module("gridx_connector.async_connector")
    async_gridbox_connector = connector_module.AsyncGridboxConnector

    connector: GridxConnector = await async_gridbox_connector.create(
        config,
        httpx_client=httpx_client,
        owns_httpx_client=True,
    )
    return connector
