"""Local storage for the Local To-do integration."""

import asyncio
import json
from pathlib import Path

from homeassistant.core import HomeAssistant


class LocalTodoListStore:
    """Local storage for a single To-do list."""

    def __init__(self, hass: HomeAssistant, path: Path) -> None:
        """Initialize LocalTodoListStore."""
        self._hass = hass
        self._path = path
        self._lock = asyncio.Lock()
        self._lock_icons = asyncio.Lock()
        self._icons_path = self._path.with_name(self._path.stem + "_icons.json")
        self._icons: dict[str, str] = {}

    async def async_load(self) -> str:
        """Load the calendar from disk."""
        async with self._lock_icons:
            await self._hass.async_add_executor_job(self._load_icons)
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
        async with self._lock_icons:
            await self._hass.async_add_executor_job(self._store_icons)

    def _store(self, ics_content: str) -> None:
        """Persist the calendar to storage."""
        self._path.write_text(ics_content)

    def _load_icons(self) -> None:
        """Load the icon mapping from disk."""
        if not self._icons_path.exists():
            self._icons = {}
            return
        content = self._icons_path.read_text()
        self._icons = json.loads(content) if content else {}

    def _store_icons(self) -> None:
        """Persist the icon mapping to storage."""
        data = json.dumps(self._icons)
        self._icons_path.write_text(data)

    def get_icon(self, uid: str) -> str | None:
        """Get the icon for a given UID."""
        return self._icons.get(uid)

    def set_icon(self, uid: str, icon: str | None) -> None:
        """Set or remove the icon for a given UID."""
        if icon:
            self._icons[uid] = icon
        elif uid in self._icons:
            del self._icons[uid]
