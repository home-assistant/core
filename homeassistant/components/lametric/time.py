"""Support for LaMetric times."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import TYPE_CHECKING, Any, override

from demetriek import DisplayScreensaverTimeBased, LaMetricDevice, ScreensaverMode

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
    set_value_fn: Callable[[LaMetricDevice, time], Awaitable[Any]]


TIMES = [
    LaMetricTimeEntityDescription(
        key="screensaver_start_time",
        translation_key="screensaver_start_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda mode: mode.start_time,
        set_value_fn=lambda api, value: api.display(
            screensaver_mode=ScreensaverMode.TIME_BASED,
            screensaver_start_time=value,
        ),
    ),
    LaMetricTimeEntityDescription(
        key="screensaver_end_time",
        translation_key="screensaver_end_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda mode: mode.end_time,
        set_value_fn=lambda api, value: api.display(
            screensaver_mode=ScreensaverMode.TIME_BASED,
            screensaver_end_time=value,
        ),
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
    @override
    def native_value(self) -> time | None:
        """Return the time value."""
        screensaver = self.coordinator.data.display.screensaver
        if TYPE_CHECKING:
            assert screensaver is not None
            assert screensaver.modes is not None

        if (
            value := self.entity_description.value_fn(screensaver.modes.time_based)
        ) is None:
            return None

        # The device stores screensaver times in UTC.
        return dt_util.as_local(
            datetime.combine(dt_util.utcnow().date(), value, tzinfo=UTC)
        ).time()

    @lametric_exception_handler
    @override
    async def async_set_value(self, value: time) -> None:
        """Change to new time value."""
        await self.entity_description.set_value_fn(
            self.coordinator.lametric,
            dt_util.as_utc(datetime.combine(dt_util.now().date(), value)).time(),
        )
        await self.coordinator.async_request_refresh()
