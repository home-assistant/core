"""Time platform for the Atomberg water purifier sleep window."""

from datetime import UTC, datetime, time, timedelta
from typing import override

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import (
    COMMAND_SLEEP_WINDOW,
    COMMAND_START_UTC,
    COMMAND_STOP_UTC,
    DEVICE_TYPE_WATER_PURIFIER,
    AtombergDevice,
)
from .coordinator import AtombergConfigEntry, AtombergCoordinator
from .entity import AtombergEntity

PARALLEL_UPDATES = 1

SECONDS_PER_DAY = 86400


def _seconds_to_local_time(seconds: int) -> time:
    """Convert a sleep window value to a local time of day."""
    utc_midnight = datetime.combine(dt_util.utcnow().date(), time(), tzinfo=UTC)
    return dt_util.as_local(
        utc_midnight + timedelta(seconds=seconds % SECONDS_PER_DAY)
    ).time()


def _local_time_to_seconds(value: time) -> int:
    """Convert a local time of day to a sleep window value."""
    local = datetime.combine(
        dt_util.now().date(), value, tzinfo=dt_util.get_default_time_zone()
    )
    return int(dt_util.as_utc(local).timestamp())


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AtombergConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Atomberg time entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        AtombergSleepWindowTime(coordinator, device, key, translation_key)
        for device in coordinator.devices_of_type(DEVICE_TYPE_WATER_PURIFIER)
        if coordinator.supports_setting(device, COMMAND_SLEEP_WINDOW)
        for key, translation_key in (
            (COMMAND_START_UTC, "sleep_window_start"),
            (COMMAND_STOP_UTC, "sleep_window_end"),
        )
    )


class AtombergSleepWindowTime(AtombergEntity, TimeEntity):
    """Start or end of the daily sleep window."""

    def __init__(
        self,
        coordinator: AtombergCoordinator,
        device: AtombergDevice,
        key: str,
        translation_key: str,
    ) -> None:
        """Initialize the time entity."""
        super().__init__(coordinator, device, key)
        self._key = key
        self._attr_translation_key = translation_key

    @property
    @override
    def native_value(self) -> time | None:
        """Return the configured time."""
        start, stop = self.coordinator.sleep_window_values(self.device.device_id)
        seconds = start if self._key == COMMAND_START_UTC else stop
        return None if seconds is None else _seconds_to_local_time(seconds)

    @override
    async def async_set_value(self, value: time) -> None:
        """Set the time."""
        await self.coordinator.async_set_sleep_window_time(
            self.device.device_id, self._key, _local_time_to_seconds(value)
        )
