"""Class representing Sonos alarms."""
from __future__ import annotations

from collections.abc import Iterator
import logging
from typing import Any

from soco import SoCo
from soco.alarms import Alarm, Alarms
from soco.exceptions import SoCoException

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DATA_SONOS, SONOS_ALARMS_UPDATED, SONOS_CREATE_ALARM
from .household_coordinator import SonosHouseholdCoordinator

_LOGGER = logging.getLogger(__name__)


class SonosAlarms(SonosHouseholdCoordinator):
    """Coordinator class for Sonos alarms."""

    def __init__(self, *args: Any) -> None:
        """Initialize the data."""
        super().__init__(*args)
        self.alarms: Alarms = Alarms()
        self.created_alarm_ids: set[str] = set()

    def __iter__(self) -> Iterator:
        """Return an iterator for the known alarms."""
        return iter(self.alarms)

    def get(self, alarm_id: str) -> Alarm | None:
        """Get an Alarm instance."""
        return self.alarms.get(alarm_id)

    async def async_update_entities(
        self, soco: SoCo, update_id: int | None = None
    ) -> None:
        """Create and update alarms entities, return success."""
        updated = await self.hass.async_add_executor_job(
            self.update_cache, soco, update_id
        )
        if not updated:
            return

        for alarm_id, alarm in self.alarms.alarms.items():
            if alarm_id in self.created_alarm_ids:
                continue
            speaker = self.hass.data[DATA_SONOS].discovered.get(alarm.zone.uid)
            if speaker:
                async_dispatcher_send(
                    self.hass, SONOS_CREATE_ALARM, speaker, [alarm_id]
                )
        async_dispatcher_send(self.hass, f"{SONOS_ALARMS_UPDATED}-{self.household_id}")

    @callback
    def async_handle_event(self, event_id: str, soco: SoCo) -> None:
        """Create a task to update from an event callback."""
        _, event_id = event_id.split(":")
        event_id = int(event_id)
        self.hass.async_create_task(self.async_process_event(event_id, soco))

    async def async_process_event(self, event_id: str, soco: SoCo) -> None:
        """Process the event payload in an async lock and update entities."""
        async with self.cache_update_lock:
            if event_id <= self.last_processed_event_id:
                # Skip updates if this event_id has already been seen
                return
            await self.async_update_entities(soco, event_id)

    def update_cache(self, soco: SoCo, update_id: int | None = None) -> bool:
        """Update cache of known alarms and return if cache has changed."""
        try:
            self.alarms.update(soco)
        except (OSError, SoCoException) as err:
            _LOGGER.error("Could not update alarms using %s: %s", soco, err)
            return False

        if update_id and self.alarms.last_id < update_id:
            # Skip updates if latest query result is outdated or lagging
            return False

        if (
            self.last_processed_event_id
            and self.alarms.last_id <= self.last_processed_event_id
        ):
            # Skip updates already processed
            return False

        _LOGGER.debug(
            "Updating processed event %s from %s (was %s)",
            self.alarms.last_id,
            soco,
            self.last_processed_event_id,
        )
        self.last_processed_event_id = self.alarms.last_id
        return True
