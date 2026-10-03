"""Support for LaMetric times."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time
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

        # The device stores screensaver times in UTC.
        return dt_util.as_local(
            datetime.combine(dt_util.utcnow().date(), value, tzinfo=UTC)
        ).time()

    @lametric_exception_handler
    @override
    async def async_set_value(self, value: time) -> None:
        """Change to new time value."""
        modes = self._modes
        new_time = dt_util.as_utc(datetime.combine(dt_util.now().date(), value)).time()
        start_time, end_time = self.entity_description.times_fn(
            modes.time_based, new_time
        )

        # The device only takes both times at once, so the one left untouched
        # is sent along. A device that never had its times set reports
        # neither; until the other one is set too, it gets the new time.
        await self.coordinator.lametric.display(
            screensaver_mode=ScreensaverMode.TIME_BASED,
            screensaver_start_time=new_time if start_time is None else start_time,
            screensaver_end_time=new_time if end_time is None else end_time,
        )

        # Writing the times always switches the device to the time based mode,
        # even when asked not to. Switch back to when dark if that was active;
        # the times stay stored.
        if modes.when_dark is not None and modes.when_dark.enabled:
            await self.coordinator.lametric.display(
                screensaver_mode=ScreensaverMode.WHEN_DARK,
                screensaver_mode_enabled=True,
            )

        await self.coordinator.async_request_refresh()
