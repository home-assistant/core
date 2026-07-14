"""Client helpers for the GridX integration."""

from importlib.resources import files
import json
from typing import Any, Protocol

from gridx_connector.async_connector import AsyncGridboxConnector
import httpx

from .const import LOGGER


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


def load_oem_config(oem: str, username: str, password: str) -> dict[str, Any]:
    """Load OEM connector config and inject credentials."""
    config_path = files("gridx_connector").joinpath("config", f"{oem}.config.json")
    config: dict[str, Any] = json.loads(config_path.read_text())
    config["login"]["username"] = username
    config["login"]["password"] = password
    return config


async def async_create_connector(
    config: dict[str, Any],
    httpx_client: httpx.AsyncClient,
) -> GridxConnector:
    """Create and initialize a GridX connector."""
    connector: GridxConnector = await AsyncGridboxConnector.create(
        config,
        logger=LOGGER,
        httpx_client=httpx_client,
        owns_httpx_client=True,
    )
    return connector
