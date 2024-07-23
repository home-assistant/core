"""History stats data coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .data import HistoryStats, HistoryStatsState

_LOGGER = logging.getLogger(__name__)


UPDATE_INTERVAL = timedelta(minutes=1)


class HistoryStatsUpdateCoordinator(DataUpdateCoordinator[HistoryStatsState]):
    """DataUpdateCoordinator to gather data for a specific TPLink device."""

    def __init__(
        self,
        hass: HomeAssistant,
        history_stats: HistoryStats,
        name: str,
    ) -> None:
        """Initialize DataUpdateCoordinator."""
        self._history_stats = history_stats
        self._subscriber_count = 0
        self._at_start_listener: CALLBACK_TYPE | None = None
        self._track_events_listener: CALLBACK_TYPE | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=UPDATE_INTERVAL,
        )

    @callback
    def async_setup_state_listener(self) -> CALLBACK_TYPE:
        """Set up listeners and return a callback to cancel them."""

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self._subscriber_count -= 1
            if self._subscriber_count == 0:
                self._async_remove_listener()

        if self._subscriber_count == 0:
            self._async_add_listener()
        self._subscriber_count += 1

        return remove_listener

    @callback
    def _async_remove_listener(self) -> None:
        """Remove state change listener."""
        if self._track_events_listener:
            self._track_events_listener()
            self._track_events_listener = None
        if self._at_start_listener:
            self._at_start_listener()
            self._at_start_listener = None

    @callback
    def _async_add_listener(self) -> None:
        """Add a listener to start tracking state changes after start."""
        self._at_start_listener = async_at_start(
            self.hass, self._async_add_events_listener
        )

    @callback
    def _async_add_events_listener(self, *_: Any) -> None:
        """Handle hass starting and start tracking events."""
        self._at_start_listener = None
        self._track_events_listener = async_track_state_change_event(
            self.hass, [self._history_stats.entity_id], self._async_update_from_event
        )

    async def _async_update_from_event(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Process an update from an event."""
        self.async_set_updated_data(await self._history_stats.async_update(event))

    async def _async_update_data(self) -> HistoryStatsState:
        """Fetch update the history stats state."""
        try:
            return await self._history_stats.async_update(None)
        except (TemplateError, TypeError, ValueError) as ex:
            raise UpdateFailed(ex) from ex
