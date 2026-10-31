"""Support for LaMetric times."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, override

from demetriek import (
    DisplayScreensaverModes,
    DisplayScreensaverTimeBased,
    ScreensaverMode,
)

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import LaMetricConfigEntry, LaMetricDataUpdateCoordinator
from .entity import LaMetricEntity
from .helpers import lametric_exception_handler

# The SKY reports a time based screensaver mode, but is not known to support
# scheduling it.
MODEL_SKY = "sa5"

# Both entities write the same pair of start and end time, so one at a time.
PARALLEL_UPDATES = 1

# Any date will do, it only carries the time arithmetic below.
TIME_ANCHOR = date(2000, 1, 1)


def _shift(value: time, offset: timedelta) -> time:
    """Shift a time of day by an offset, wrapping around midnight."""
    return (datetime.combine(TIME_ANCHOR, value) + offset).time()


def _utc_offset() -> timedelta:
    """Return the current offset of the Home Assistant time zone from UTC.

    The device stores the screensaver times in UTC. Converting both ways with
    the same, current offset makes reading the exact inverse of writing, also
    around a DST change, where going by today's date would not be.
    """
    return dt_util.now().utcoffset() or timedelta()


@dataclass(frozen=True, kw_only=True)
class LaMetricTimeEntityDescription(TimeEntityDescription):
    """Class describing LaMetric time entities."""

    value_fn: Callable[[DisplayScreensaverTimeBased], time | None]
    times_fn: Callable[
        [DisplayScreensaverTimeBased, time], tuple[time | None, time | None]
    ]


TIMES = [
    LaMetricTimeEntityDescription(
        key="screensaver_start_time",
        translation_key="screensaver_start_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda mode: mode.start_time,
        times_fn=lambda mode, value: (value, mode.end_time),
    ),
    LaMetricTimeEntityDescription(
        key="screensaver_end_time",
        translation_key="screensaver_end_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda mode: mode.end_time,
        times_fn=lambda mode, value: (mode.start_time, value),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMetricConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LaMetric time based on a config entry."""
    coordinator = entry.runtime_data
    if coordinator.data.model == MODEL_SKY:
        return

    screensaver = coordinator.data.display.screensaver
    if not screensaver or not screensaver.modes:
        return

    async_add_entities(
        LaMetricTimeEntity(
            coordinator=coordinator,
            description=description,
        )
        for description in TIMES
    )


class LaMetricTimeEntity(LaMetricEntity, TimeEntity):
    """Representation of a LaMetric time."""

    entity_description: LaMetricTimeEntityDescription

    def __init__(
        self,
        coordinator: LaMetricDataUpdateCoordinator,
        description: LaMetricTimeEntityDescription,
    ) -> None:
        """Initiate LaMetric Time."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.serial_number}-{description.key}"

    @property
    def _modes(self) -> DisplayScreensaverModes:
        """Return the screensaver modes of the device."""
        screensaver = self.coordinator.data.display.screensaver
        if TYPE_CHECKING:
            assert screensaver is not None
            assert screensaver.modes is not None
        return screensaver.modes

    @property
    @override
    def native_value(self) -> time | None:
        """Return the time value."""
        if (value := self.entity_description.value_fn(self._modes.time_based)) is None:
            return None

        return _shift(value, _utc_offset())

    @lametric_exception_handler
    @override
    async def async_set_value(self, value: time) -> None:
        """Change to new time value."""
        modes = self._modes
        new_time = _shift(value, -_utc_offset())
        start_time, end_time = self.entity_description.times_fn(
            modes.time_based, new_time
        )

        # The device only takes both times at once, so the one left untouched
        # is sent along. A device that never had its times set reports
        # neither; until the other one is set too, it gets the new time.
        display = await self.coordinator.lametric.display(
            screensaver_mode=ScreensaverMode.TIME_BASED,
            screensaver_start_time=new_time if start_time is None else start_time,
            screensaver_end_time=new_time if end_time is None else end_time,
        )

        # Writing the times always switches the device to the time based mode,
        # even when asked not to. Switch back to when dark if that was active;
        # the times stay stored.
        if modes.when_dark is not None and modes.when_dark.enabled:
            display = await self.coordinator.lametric.display(
                screensaver_mode=ScreensaverMode.WHEN_DARK,
                screensaver_mode_enabled=True,
            )

        # The device answers with its new state, use that right away. A refresh
        # requested shortly after the previous one is held back, and the next
        # write would send a stale time along otherwise.
        self.coordinator.async_set_updated_data(
            replace(self.coordinator.data, display=display)
        )
