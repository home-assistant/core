"""Support for LaMetric times."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import Any, override

from demetriek import Device, LaMetricDevice, ScreensaverMode

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import LaMetricConfigEntry, LaMetricDataUpdateCoordinator
from .entity import LaMetricEntity
from .helpers import lametric_exception_handler


@dataclass(frozen=True, kw_only=True)
class LaMetricTimeEntityDescription(TimeEntityDescription):
    """Class describing LaMetric time entities."""

    has_fn: Callable[[Device], bool] = lambda device: True
    value_fn: Callable[[Device], time | None]
    set_value_fn: Callable[[LaMetricDevice, time], Awaitable[Any]]


def _has_screensaver_modes(device: Device) -> bool:
    """Return if the device reports its screensaver modes."""
    return bool(device.display.screensaver and device.display.screensaver.modes)


TIMES = [
    LaMetricTimeEntityDescription(
        key="screensaver_start_time",
        translation_key="screensaver_start_time",
        entity_category=EntityCategory.CONFIG,
        has_fn=_has_screensaver_modes,
        value_fn=lambda device: (
            screensaver.modes.time_based.start_time
            if (screensaver := device.display.screensaver) and screensaver.modes
            else None
        ),
        set_value_fn=lambda api, value: api.display(
            screensaver_mode=ScreensaverMode.TIME_BASED,
            screensaver_start_time=value,
        ),
    ),
    LaMetricTimeEntityDescription(
        key="screensaver_end_time",
        translation_key="screensaver_end_time",
        entity_category=EntityCategory.CONFIG,
        has_fn=_has_screensaver_modes,
        value_fn=lambda device: (
            screensaver.modes.time_based.end_time
            if (screensaver := device.display.screensaver) and screensaver.modes
            else None
        ),
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
    async_add_entities(
        LaMetricTimeEntity(
            coordinator=coordinator,
            description=description,
        )
        for description in TIMES
        if description.has_fn(coordinator.data)
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
        if (value := self.entity_description.value_fn(self.coordinator.data)) is None:
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
