"""Support for LaMetric times."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import TYPE_CHECKING, override

from demetriek import DisplayScreensaverTimeBased, ScreensaverMode

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
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
    def _time_based(self) -> DisplayScreensaverTimeBased:
        """Return the time based screensaver mode of the device."""
        screensaver = self.coordinator.data.display.screensaver
        if TYPE_CHECKING:
            assert screensaver is not None
            assert screensaver.modes is not None
        return screensaver.modes.time_based

    @property
    @override
    def native_value(self) -> time | None:
        """Return the time value."""
        if (value := self.entity_description.value_fn(self._time_based)) is None:
            return None

        # The device stores screensaver times in UTC.
        return dt_util.as_local(
            datetime.combine(dt_util.utcnow().date(), value, tzinfo=UTC)
        ).time()

    @lametric_exception_handler
    @override
    async def async_set_value(self, value: time) -> None:
        """Change to new time value."""
        start_time, end_time = self.entity_description.times_fn(
            self._time_based,
            dt_util.as_utc(datetime.combine(dt_util.now().date(), value)).time(),
        )

        # The device rejects a time based write that carries only one of the
        # times, so the one left untouched has to be sent along.
        if start_time is None or end_time is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="screensaver_times_incomplete",
            )

        await self.coordinator.lametric.display(
            screensaver_mode=ScreensaverMode.TIME_BASED,
            screensaver_start_time=start_time,
            screensaver_end_time=end_time,
        )
        await self.coordinator.async_request_refresh()
