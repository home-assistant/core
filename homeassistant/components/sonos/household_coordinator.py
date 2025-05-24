"""Class representing a Sonos household storage helper."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import logging
from typing import TYPE_CHECKING, Any

from soco import SoCo

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer

from .exception import SonosUpdateError

if TYPE_CHECKING:
    from .config_entry import SonosConfigEntry

_LOGGER = logging.getLogger(__name__)


class SonosHouseholdCoordinator:
    """Base class for Sonos household-level storage."""

    cache_update_lock: asyncio.Lock

    def __init__(
        self, hass: HomeAssistant, household_id: str, config_entry: SonosConfigEntry
    ) -> None:
        """Initialize the data."""
        self.hass = hass
        self.household_id = household_id
        self.async_poll: Callable[[], Coroutine[None, None, None]] | None = None
        self.last_processed_event_id: int | None = None
        self.config_entry = config_entry

    def setup(self, soco: SoCo) -> None:
        """Set up the SonosAlarm instance."""
        self.update_cache(soco)
        self.hass.add_job(self._async_setup)

    @callback
    def _async_setup(self) -> None:
        """Finish setup in async context."""
        self.cache_update_lock = asyncio.Lock()
        self.async_poll = Debouncer[Coroutine[Any, Any, None]](
            self.hass,
            _LOGGER,
            cooldown=3,
            immediate=False,
            function=self._async_poll,
        ).async_call

    @property
    def class_type(self) -> str:
        """Return the class type of this instance."""
        return type(self).__name__

    async def _async_poll(self) -> None:
        """Poll any known speaker."""
        discovered = self.config_entry.runtime_data.sonos_data.discovered

        for uid, speaker in discovered.items():
            _LOGGER.debug("Polling %s using %s", self.class_type, speaker.soco)
            try:
                await self.async_update_entities(speaker.soco)
            except SonosUpdateError as err:
                _LOGGER.error(
                    "Could not refresh %s: %s",
                    self.class_type,
                    err,
                )
            else:
                # Prefer this SoCo instance next update
                discovered.move_to_end(uid, last=False)
                break

    async def async_update_entities(
        self, soco: SoCo, update_id: int | None = None
    ) -> None:
        """Update the cache and update entities."""
        raise NotImplementedError

    def update_cache(self, soco: SoCo, update_id: int | None = None) -> bool:
        """Update the cache of the household-level feature and return if cache has changed."""
        raise NotImplementedError
