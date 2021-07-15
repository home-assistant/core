"""Class representing Sonos alarms."""
from __future__ import annotations

from collections.abc import Iterator
import logging
from typing import Any

from pysonos import SoCo
from pysonos.alarms import Alarm, get_alarms
from pysonos.exceptions import SoCoException

from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DATA_SONOS, SONOS_ALARMS_UPDATED, SONOS_CREATE_ALARM
from .household_coordinator import SonosHouseholdCoordinator

_LOGGER = logging.getLogger(__name__)


class SonosAlarms(SonosHouseholdCoordinator):
    """Coordinator class for Sonos alarms."""

    def __init__(self, *args: Any) -> None:
        """Initialize the data."""
        super().__init__(*args)
        self._alarms: dict[str, Alarm] = {}

    def __iter__(self) -> Iterator:
        """Return an iterator for the known alarms."""
        alarms = list(self._alarms.values())
        return iter(alarms)

    def get(self, alarm_id: str) -> Alarm | None:
        """Get an Alarm instance."""
        return self._alarms.get(alarm_id)

    async def async_update_entities(self, soco: SoCo) -> bool:
        """Create and update alarms entities, return success."""
        try:
            new_alarms = await self.hass.async_add_executor_job(self.update_cache, soco)
        except (OSError, SoCoException) as err:
            _LOGGER.error("Could not refresh alarms using %s: %s", soco, err)
            return False

        for alarm in new_alarms:
            speaker = self.hass.data[DATA_SONOS].discovered[alarm.zone.uid]
            async_dispatcher_send(
                self.hass, SONOS_CREATE_ALARM, speaker, [alarm.alarm_id]
            )
        async_dispatcher_send(self.hass, f"{SONOS_ALARMS_UPDATED}-{self.household_id}")
        return True

    def update_cache(self, soco: SoCo) -> set[Alarm]:
        """Populate cache of known alarms.

        Prune deleted alarms and return new alarms.
        """
        soco_alarms = get_alarms(soco)
        new_alarms = set()

        for alarm in soco_alarms:
            if alarm.alarm_id not in self._alarms:
                new_alarms.add(alarm)
                self._alarms[alarm.alarm_id] = alarm

        for alarm_id, alarm in list(self._alarms.items()):
            if alarm not in soco_alarms:
                self._alarms.pop(alarm_id)

        return new_alarms
