"""Local storage for the Local To-do integration."""

import asyncio
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers.os_error import os_write_error


class LocalTodoListStore:
    """Local storage for a single To-do list."""

    def __init__(self, hass: HomeAssistant, path: Path) -> None:
        """Initialize LocalTodoListStore."""
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
        return self._path.read_text(encoding="utf-8")

    async def async_store(self, ics_content: str) -> None:
        """Persist the calendar to storage."""
        async with self._lock:
            try:
                await self._hass.async_add_executor_job(self._store, ics_content)
            except OSError as err:
                raise os_write_error(err, str(self._path)) from err

    def _store(self, ics_content: str) -> None:
        """Persist the calendar to storage."""
        self._path.write_text(ics_content, encoding="utf-8")
