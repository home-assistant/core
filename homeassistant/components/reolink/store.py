"""Local storage for the Reolink integration."""

import asyncio
from pathlib import Path
from homeassistant.core import HomeAssistant
import logging

_LOGGER = logging.getLogger(__name__)

class ReolinkStore:
    """Local storage for Reolink."""

    def __init__(self, hass: HomeAssistant, config_id: str)) -> None:
        """Initialize ReolinkStore."""
        self._hass = hass
        self._path = Path(hass.config.path(f".storage/reolink.{config_id}.json"))
        self._lock = asyncio.Lock()

    async def async_load(self) -> str:
        """Load the data from disk."""
        async with self._lock:
            return await self._hass.async_add_executor_job(self._load)

    def _load(self) -> str:
        """Load the data from disk."""
        if not self._path.exists():
            _LOGGER.debug("Failed to load file %s: path does not exist", self._path)
            return "{}"

        try:
            return self._path.read_text()
        except OSError as err:
            _LOGGER.debug("Failed to load file %s: %s", self._path, err)
            return "{}"

    async def async_store(self, data: str) -> None:
        """Persist the data to storage."""
        async with self._lock:
            await self._hass.async_add_executor_job(self._store, data)

    def _store(self, data: str) -> None:
        """Persist the data to storage."""
        self._path.write_text(data)
