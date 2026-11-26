"""Google Calendar local storage."""

from dataclasses import dataclass
import logging
from typing import Any, override

from gcal_sync.api import GoogleCalendarService
from gcal_sync.store import CalendarStore

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY_FORMAT = "{domain}.{entry_id}"
STORAGE_VERSION = 2
# Buffer writes every few minutes (plus guaranteed to be written at shutdown)
STORAGE_SAVE_DELAY_SECONDS = 120

type GoogleConfigEntry = ConfigEntry[GoogleRuntimeData]


@dataclass
class GoogleRuntimeData:
    """Google runtime data."""

    service: GoogleCalendarService
    store: LocalCalendarStore


class _GoogleCalendarStore(Store[dict[str, Any]]):
    """Store for Google Calendar data with migration support."""

    @override
    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Migrate from older storage versions."""
        # Drop the cache on migration so the client library performs a full
        # re-sync of all content into the new storage layout.
        return {}


class LocalCalendarStore(CalendarStore):
    """Storage for local persistence of calendar and event data."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize LocalCalendarStore."""
        self._store = _GoogleCalendarStore(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY_FORMAT.format(domain=DOMAIN, entry_id=entry_id),
            private=True,
        )
        self._data: dict[str, Any] | None = None

    @override
    async def async_load(self) -> dict[str, Any] | None:
        """Load data."""
        if self._data is None:
            self._data = await self._store.async_load() or {}
        return self._data

    @override
    async def async_save(self, data: dict[str, Any]) -> None:
        """Save data."""
        self._data = data

        def provide_data() -> dict:
            return data

        self._store.async_delay_save(provide_data, STORAGE_SAVE_DELAY_SECONDS)

    async def async_flush(self) -> None:
        """Write cached data and finish pending saves before unloading."""
        if self._data is not None:
            await self._store.async_save(self._data)

    async def async_remove(self) -> None:
        """Remove persisted data and prevent further writes."""
        self._store.make_read_only()
        # Wait for active writes before removing the file.
        await self.async_flush()
        await self._store.async_remove()
