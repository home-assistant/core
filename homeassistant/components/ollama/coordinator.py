"""Data update coordinator for the Ollama integration."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Final, override

import httpx
import ollama

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL: Final = timedelta(seconds=30)


@dataclass(frozen=True)
class OllamaData:
    """Data returned by Ollama."""

    loaded: ollama.ProcessResponse
    installed: ollama.ListResponse


class OllamaDataUpdateCoordinator(DataUpdateCoordinator[OllamaData]):
    """Coordinate updates from Ollama."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, client: ollama.AsyncClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    @override
    async def _async_update_data(self) -> OllamaData:
        """Fetch data from Ollama."""
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                installed = await self.client.list()
                loaded = await self.client.ps()
        except (
            TimeoutError,
            httpx.HTTPError,
            ollama.ResponseError,
            ConnectionError,
        ) as err:
            raise UpdateFailed(f"Error communicating with Ollama: {err}") from err

        return OllamaData(loaded, installed)
