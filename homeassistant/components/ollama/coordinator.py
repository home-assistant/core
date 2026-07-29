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
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL: Final = timedelta(seconds=30)


@dataclass(frozen=True)
class OllamaData:
    """Data returned by Ollama."""

    loaded: ollama.ProcessResponse | None
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
        except ollama.ResponseError as err:
            if err.status_code in (401, 403):
                raise ConfigEntryAuthFailed from err
            if err.status_code >= 500 or err.status_code == 429:
                raise UpdateFailed(f"Error communicating with Ollama: {err}") from err
            # Other 4xx errors likely mean the URL is not an Ollama instance.
            raise ConfigEntryError(err) from err
        except (TimeoutError, httpx.HTTPError, ConnectionError) as err:
            raise UpdateFailed(f"Error communicating with Ollama: {err}") from err

        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                loaded = await self.client.ps()
        except ollama.ResponseError as err:
            if err.status_code in (401, 403):
                raise ConfigEntryAuthFailed from err
            _LOGGER.error("Error fetching loaded models from Ollama: %s", err)
            loaded = None
        except (TimeoutError, httpx.HTTPError, ConnectionError) as err:
            _LOGGER.error("Error fetching loaded models from Ollama: %s", err)
            loaded = None

        return OllamaData(loaded, installed)
