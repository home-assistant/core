"""Support for representing daily schedule as binary sensors."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import event as event_helper
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import ATTR_SCHEDULE
from .schedule import Schedule


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry."""
    async_add_entities(
        [
            DailyScheduleSenosr(
                config_entry.title,
                config_entry.entry_id,
                config_entry.options.get(ATTR_SCHEDULE, []),
            )
        ]
    )


class DailyScheduleSenosr(BinarySensorEntity):
    """Representation of a daily schedule sensor."""

    _attr_icon = "mdi:timetable"

    def __init__(
        self, name: str, unique_id: str, schedule: list[dict[str, str]]
    ) -> None:
        """Initialize object with defaults."""
        self._name = name
        self._attr_unique_id = unique_id
        self._schedule: Schedule = Schedule(schedule)
        self._unsub_update: CALLBACK_TYPE | None = None

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return True is sensor is on."""
        return self._schedule.containing(dt_util.now().time())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the sensor."""
        return {
            ATTR_SCHEDULE: self._schedule.to_list(),
        }

    @callback
    def _clean_up_listener(self):
        """Remove the update timer."""
        if self._unsub_update is not None:
            self._unsub_update()
            self._unsub_update = None

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(self._clean_up_listener)
        self._update_state()

    def _schedule_update(self) -> None:
        """Schedule a timer for the point when the state should be changed."""
        self._clean_up_listener()

        next_update = self._schedule.next_update(dt_util.now())
        if not next_update:
            return

        self._unsub_update = event_helper.async_track_point_in_time(
            self.hass, self._update_state, next_update
        )

    @callback
    def _update_state(self, *_):
        """Update the state to reflect the current time."""
        self._schedule_update()
        self.async_write_ha_state()
