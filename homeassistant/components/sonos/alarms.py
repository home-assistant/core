"""Class representing Sonos alarms."""

from __future__ import annotations

from collections.abc import Iterator
import logging
from typing import TYPE_CHECKING, Any

from soco import SoCo
from soco.alarms import Alarm, Alarms
from soco.events_base import Event as SonosEvent

from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import SONOS_ALARMS_UPDATED, SONOS_CREATE_ALARM
from .helpers import soco_error
from .household_coordinator import SonosHouseholdCoordinator

if TYPE_CHECKING:
    from .speaker import SonosSpeaker

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
            speaker = self.config_entry.runtime_data.sonos_data.discovered.get(
                alarm.zone.uid
            )
            if speaker:
                async_dispatcher_send(
                    self.hass, SONOS_CREATE_ALARM, speaker, [alarm_id]
                )
        async_dispatcher_send(self.hass, f"{SONOS_ALARMS_UPDATED}-{self.household_id}")

    async def async_process_event(
        self, event: SonosEvent, speaker: SonosSpeaker
    ) -> None:
        """Process the event payload in an async lock and update entities."""
        event_id = event.variables["alarm_list_version"].split(":")[-1]
        event_id = int(event_id)
        async with self.cache_update_lock:
            if (
                self.last_processed_event_id
                and event_id <= self.last_processed_event_id
            ):
                # Skip updates if this event_id has already been seen
                return
            speaker.event_stats.process(event)
            await self.async_update_entities(speaker.soco, event_id)

    @soco_error()
    def update_cache(self, soco: SoCo, update_id: int | None = None) -> bool:
        """Update cache of known alarms and return if cache has changed."""
        self.alarms.update(soco)

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
