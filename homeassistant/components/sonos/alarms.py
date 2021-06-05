"""Class representing Sonos alarms."""
from __future__ import annotations

from collections import deque
from collections.abc import Iterator
import logging
from typing import Callable

from pysonos import SoCo
from pysonos.alarms import Alarm, get_alarms
from pysonos.events_base import Event as SonosEvent
from pysonos.exceptions import SoCoException

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DATA_SONOS, SONOS_ALARM_UPDATE, SONOS_CREATE_ALARM

_LOGGER = logging.getLogger(__name__)


class SonosAlarms:
    """Storage class for Sonos alarms."""

    def __init__(self, hass: HomeAssistant, household_id: str) -> None:
        """Initialize the data."""
        self.hass = hass
        self.household_id = household_id
        self._alarms: dict[str, Alarm] = {}
        self._next_update: Callable | None = None
        self._processed_events = deque(maxlen=5)

    def __iter__(self) -> Iterator:
        """Return an iterator for the known alarms."""
        alarms = list(self._alarms.values())
        return iter(alarms)

    def get(self, alarm_id: str) -> Alarm | None:
        """Get an Alarm instance."""
        return self._alarms.get(alarm_id)

    @callback
    def async_refresh(self, event: SonosEvent, soco: SoCo) -> None:
        """Create a task to update alarms from an event callback."""
        if not (update_id := event.variables.get("alarm_list_version")):
            return
        if update_id in self._processed_events:
            return
        self._processed_events.append(update_id)
        self.hass.async_create_task(self._async_refresh(soco))

    async def _async_refresh(self, soco: SoCo) -> None:
        """Create and update alarms."""
        new_alarms = await self.hass.async_add_executor_job(self.get_new_alarms, soco)
        for alarm in new_alarms:
            speaker = self.hass.data[DATA_SONOS].discovered[alarm.zone.uid]
            async_dispatcher_send(self.hass, SONOS_CREATE_ALARM, speaker, [alarm])
        async_dispatcher_send(self.hass, f"{SONOS_ALARM_UPDATE}-{self.household_id}")

    def get_new_alarms(self, soco: SoCo) -> set[Alarm]:
        """Populate cache of known alarms.

        Prune deleted alarms and return new alarms.
        """
        new_alarms = set()
        try:
            soco_alarms = get_alarms(soco)
        except (OSError, SoCoException) as exc:
            _LOGGER.error("Could not refresh alarms from %s: %s", soco, exc)

        for alarm in soco_alarms:
            if alarm.alarm_id not in self._alarms:
                new_alarms.add(alarm)
                self._alarms[alarm.alarm_id] = alarm

        for alarm_id, alarm in list(self._alarms.items()):
            if alarm not in soco_alarms:
                self._alarms.pop(alarm_id)

        return new_alarms
