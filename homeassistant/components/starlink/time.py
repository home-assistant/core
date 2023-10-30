"""Contains time pickers exposed by the Starlink integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, time
import math

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import StarlinkData, StarlinkUpdateCoordinator
from .entity import StarlinkEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up all binary sensors for this entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        StarlinkTimeEntity(coordinator, description) for description in TIMES
    )


@dataclass
class StarlinkTimeEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[StarlinkData], time | None]
    update_fn: Callable[[StarlinkUpdateCoordinator, time], Awaitable[None]]
    available_fn: Callable[[StarlinkData], bool]


@dataclass
class StarlinkTimeEntityDescription(
    TimeEntityDescription, StarlinkTimeEntityDescriptionMixin
):
    """Describes a Starlink switch entity."""


class StarlinkTimeEntity(StarlinkEntity, TimeEntity):
    """A TimeEntity for Starlink devices. Handles creating unique IDs."""

    entity_description: StarlinkTimeEntityDescription

    @property
    def native_value(self) -> time | None:
        """Return the value reported by the time."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.entity_description.available_fn(self.coordinator.data)

    async def async_set_value(self, value: time) -> None:
        """Change the time."""
        return await self.entity_description.update_fn(self.coordinator, value)


def _utc_minutes_to_time(utc_minutes: int) -> time:
    hour = math.floor(utc_minutes / 60)
    minute = utc_minutes % 60
    utc = time(hour=hour, minute=minute, tzinfo=UTC)
    return utc


def _time_to_utc_minutes(t: time) -> int:
    return (t.hour * 60) + t.minute


TIMES = [
    StarlinkTimeEntityDescription(
        key="sleep_start",
        translation_key="sleep_start",
        value_fn=lambda data: _utc_minutes_to_time(data.sleep[0]),
        update_fn=lambda coordinator, time: coordinator.async_set_sleep_start(
            _time_to_utc_minutes(time)
        ),
        available_fn=lambda data: data.sleep[2],
    ),
    StarlinkTimeEntityDescription(
        key="sleep_end",
        translation_key="sleep_end",
        value_fn=lambda data: _utc_minutes_to_time(data.sleep[0] + data.sleep[1]),
        update_fn=lambda coordinator, time: coordinator.async_set_sleep_duration(
            _time_to_utc_minutes(time)
        ),
        available_fn=lambda data: data.sleep[2],
    ),
]
