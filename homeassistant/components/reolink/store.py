"""Local storage for the Reolink integration."""

import asyncio
import logging
from pathlib import Path

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ReolinkStore:
    """Local storage for Reolink."""

    def __init__(self, hass: HomeAssistant, config_id: str) -> None:
        """Initialize ReolinkStore."""
        self._hass = hass
        self._path = Path(hass.config.path(f".storage/{DOMAIN}/{config_id}.json"))
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
            return self._path.read_text(encoding="utf-8")
        except OSError as err:
            _LOGGER.debug("Failed to load file %s: %s", self._path, err)
            return "{}"

    async def async_store(self, data: str) -> None:
        """Persist the data to storage."""
        async with self._lock:
            await self._hass.async_add_executor_job(self._store, data)

    def _store(self, data: str) -> None:
        """Persist the data to storage."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as err:
            _LOGGER.error("Failed to create map directory %s: %s", self._path, err)
            return

        try:
            self._path.write_text(data, encoding="utf-8")
        except OSError as err:
            _LOGGER.error("Failed to save file %s: %s", self._path, err)

    async def async_remove(self) -> None:
        """Remove storage file associated with the config entry."""
        async with self._lock:
            await self._hass.async_add_executor_job(self._remove)

    def remove(self) -> None:
        """Remove storage file associated with the config entry."""
        try:
            if self._path.exists():
                self._path.unlink(missing_ok=True)

            is_empty = not any(self._path.parent.iterdir())
            if is_empty:
                self._path.parent.rmdir()
        except OSError as err:
            _LOGGER.error("Failed to remove file %s: %s", self._path, err)
