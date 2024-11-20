"""Local storage for the Local Calendar integration."""

import asyncio
from pathlib import Path

from homeassistant.core import HomeAssistant

STORAGE_PATH = ".storage/{key}.ics"


class LocalCalendarStore:
    """Local calendar storage."""

    def __init__(self, hass: HomeAssistant, path: Path) -> None:
        """Initialize LocalCalendarStore."""
        self._hass = hass
        self._path = path
        self._lock = asyncio.Lock()

    async def async_load(self) -> str:
        """Load the calendar from disk."""
        async with self._lock:
            return await self._hass.async_add_executor_job(self._load)

    def _load(self) -> str:
        """Load the calendar from disk."""
        if not self._path.exists():
            return ""
        return self._path.read_text()

    async def async_store(self, ics_content: str) -> None:
        """Persist the calendar to storage."""
        async with self._lock:
            await self._hass.async_add_executor_job(self._store, ics_content)

    def _store(self, ics_content: str) -> None:
        """Persist the calendar to storage."""
        self._path.write_text(ics_content)
