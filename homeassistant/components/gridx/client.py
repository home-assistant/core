"""Client helpers for the GridX integration."""

from importlib.resources import files
import json
from typing import Any

from gridx_connector.async_connector import AsyncGridboxConnector
import httpx

from .const import LOGGER, OEM


def load_oem_config(username: str, password: str) -> dict[str, Any]:
    """Load the packaged OEM endpoint config and inject the credentials."""
    config_path = files("gridx_connector").joinpath("config", f"{OEM}.config.json")
    config: dict[str, Any] = json.loads(config_path.read_text())
    config["login"]["username"] = username
    config["login"]["password"] = password
    return config


async def async_create_connector(
    config: dict[str, Any],
    httpx_client: httpx.AsyncClient,
) -> AsyncGridboxConnector:
    """Create and initialize a GridX connector."""
    return await AsyncGridboxConnector.create(
        config,
        logger=LOGGER,
        httpx_client=httpx_client,
        owns_httpx_client=True,
    )
