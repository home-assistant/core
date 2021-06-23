"""Class representing a Sonos household storage helper."""
from __future__ import annotations

from collections import deque
from collections.abc import Callable, Coroutine
import logging
from typing import Any

from pysonos import SoCo

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer

from .const import DATA_SONOS

_LOGGER = logging.getLogger(__name__)


class SonosHouseholdCoordinator:
    """Base class for Sonos household-level storage."""

    def __init__(self, hass: HomeAssistant, household_id: str) -> None:
        """Initialize the data."""
        self.hass = hass
        self.household_id = household_id
        self._processed_events = deque(maxlen=5)
        self.async_poll: Callable[[], Coroutine[None, None, None]] | None = None

    def setup(self, soco: SoCo) -> None:
        """Set up the SonosAlarm instance."""
        self.update_cache(soco)
        self.hass.add_job(self._async_create_polling_debouncer)

    async def _async_create_polling_debouncer(self) -> None:
        """Create a polling debouncer in async context.

        Used to ensure redundant poll requests from all speakers are coalesced.
        """
        self.async_poll = Debouncer(
            self.hass,
            _LOGGER,
            cooldown=3,
            immediate=False,
            function=self._async_poll,
        ).async_call

    async def _async_poll(self) -> None:
        """Poll any known speaker."""
        discovered = self.hass.data[DATA_SONOS].discovered

        for uid, speaker in discovered.items():
            _LOGGER.debug("Updating %s using %s", type(self).__name__, speaker.soco)
            success = await self.async_update_entities(speaker.soco)

            if success:
                # Prefer this SoCo instance next update
                discovered.move_to_end(uid, last=False)
                break

    @callback
    def async_handle_event(self, event_id: str, soco: SoCo) -> None:
        """Create a task to update from an event callback."""
        if event_id in self._processed_events:
            return
        self._processed_events.append(event_id)
        self.hass.async_create_task(self.async_update_entities(soco))

    async def async_update_entities(self, soco: SoCo) -> bool:
        """Update the cache and update entities."""
        raise NotImplementedError()

    def update_cache(self, soco: SoCo) -> Any:
        """Update the cache of the household-level feature."""
        raise NotImplementedError()
