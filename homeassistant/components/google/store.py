"""Google Calendar local storage."""

from __future__ import annotations

import logging
from typing import Any

from gcal_sync.store import CalendarStore

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY_FORMAT = "{domain}.{entry_id}"
STORAGE_VERSION = 1
# Buffer writes every few minutes (plus guaranteed to be written at shutdown)
STORAGE_SAVE_DELAY_SECONDS = 120


class LocalCalendarStore(CalendarStore):
    """Storage for local persistence of calendar and event data."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize LocalCalendarStore."""
        self._store = Store[dict[str, Any]](
            hass,
            STORAGE_VERSION,
            STORAGE_KEY_FORMAT.format(domain=DOMAIN, entry_id=entry_id),
            private=True,
        )
        self._data: dict[str, Any] | None = None

    async def async_load(self) -> dict[str, Any] | None:
        """Load data."""
        if self._data is None:
            self._data = await self._store.async_load() or {}
        return self._data

    async def async_save(self, data: dict[str, Any]) -> None:
        """Save data."""
        self._data = data

        def provide_data() -> dict:
            return data

        self._store.async_delay_save(provide_data, STORAGE_SAVE_DELAY_SECONDS)

    async def async_remove(self) -> None:
        """Remove data."""
        await self._store.async_remove()
