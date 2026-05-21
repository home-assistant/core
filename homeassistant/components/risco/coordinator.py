"""Coordinator for the Risco integration."""

from datetime import timedelta
import logging
from typing import Any, override

from pyrisco import CannotConnectError, OperationError, RiscoCloud, UnauthorizedError
from pyrisco.cloud.event import Event

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

LAST_EVENT_STORAGE_VERSION = 1
LAST_EVENT_TIMESTAMP_KEY = "last_event_timestamp"
_LOGGER = logging.getLogger(__name__)


class RiscoEventsDataUpdateCoordinator(DataUpdateCoordinator[list[Event]]):
    """Class to manage fetching risco data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        risco: RiscoCloud,
    ) -> None:
        """Initialize global risco data updater."""
        self.risco = risco
        self._store = Store[dict[str, Any]](
            hass,
            LAST_EVENT_STORAGE_VERSION,
            f"risco_{config_entry.entry_id}_last_event_timestamp",
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_events",
            update_interval=timedelta(seconds=60),
        )

    @override
    async def _async_update_data(self) -> list[Event]:
        """Fetch data from risco."""
        last_store = await self._store.async_load() or {}
        last_timestamp = last_store.get(
            LAST_EVENT_TIMESTAMP_KEY, "2020-01-01T00:00:00Z"
        )
        try:
            events = await self.risco.get_events(last_timestamp, 10)
        except (CannotConnectError, UnauthorizedError, OperationError) as error:
            raise UpdateFailed(error) from error

        if len(events) > 0:
            await self._store.async_save({LAST_EVENT_TIMESTAMP_KEY: events[0].time})

        return events
