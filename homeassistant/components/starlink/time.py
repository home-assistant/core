"""Contains time pickers exposed by the Starlink integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time, tzinfo
import math

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import StarlinkData, StarlinkUpdateCoordinator
from .entity import StarlinkEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up all time entities for this entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        StarlinkTimeEntity(coordinator, description) for description in TIMES
    )


@dataclass(frozen=True, kw_only=True)
class StarlinkTimeEntityDescription(TimeEntityDescription):
    """Describes a Starlink time entity."""

    value_fn: Callable[[StarlinkData, tzinfo], time | None]
    update_fn: Callable[[StarlinkUpdateCoordinator, time], Awaitable[None]]
    available_fn: Callable[[StarlinkData], bool]


class StarlinkTimeEntity(StarlinkEntity, TimeEntity):
    """A TimeEntity for Starlink devices. Handles creating unique IDs."""

    entity_description: StarlinkTimeEntityDescription

    @property
    def native_value(self) -> time | None:
        """Return the value reported by the time."""
        return self.entity_description.value_fn(
            self.coordinator.data, self.coordinator.timezone
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.entity_description.available_fn(self.coordinator.data)

    async def async_set_value(self, value: time) -> None:
        """Change the time."""
        return await self.entity_description.update_fn(self.coordinator, value)


def _utc_minutes_to_time(utc_minutes: int, timezone: tzinfo) -> time:
    hour = math.floor(utc_minutes / 60)
    if hour > 23:
        hour -= 24
    minute = utc_minutes % 60
    try:
        utc = datetime.now(UTC).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
    except ValueError as exc:
        raise HomeAssistantError from exc
    return utc.astimezone(timezone).time()


def _time_to_utc_minutes(t: time, timezone: tzinfo) -> int:
    try:
        zoned_time = datetime.now(timezone).replace(
            hour=t.hour, minute=t.minute, second=0, microsecond=0
        )
    except ValueError as exc:
        raise HomeAssistantError from exc
    utc_time = zoned_time.astimezone(UTC).time()
    return (utc_time.hour * 60) + utc_time.minute


TIMES = [
    StarlinkTimeEntityDescription(
        key="sleep_start",
        translation_key="sleep_start",
        value_fn=lambda data, timezone: _utc_minutes_to_time(data.sleep[0], timezone),
        update_fn=lambda coordinator, time: coordinator.async_set_sleep_start(
            _time_to_utc_minutes(time, coordinator.timezone)
        ),
        available_fn=lambda data: data.sleep[2],
    ),
    StarlinkTimeEntityDescription(
        key="sleep_end",
        translation_key="sleep_end",
        value_fn=lambda data, timezone: _utc_minutes_to_time(
            data.sleep[0] + data.sleep[1], timezone
        ),
        update_fn=lambda coordinator, time: coordinator.async_set_sleep_duration(
            _time_to_utc_minutes(time, coordinator.timezone)
        ),
        available_fn=lambda data: data.sleep[2],
    ),
]
