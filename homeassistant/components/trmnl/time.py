"""Support for TRMNL time entities."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import time
from typing import Any

from trmnl.models import Device

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TRMNLConfigEntry
from .coordinator import TRMNLCoordinator
from .entity import TRMNLEntity, exception_handler

PARALLEL_UPDATES = 0


def _minutes_to_time(minutes: int) -> time:
    """Convert minutes since midnight to a time object."""
    return time(hour=minutes // 60, minute=minutes % 60)


def _time_to_minutes(value: time) -> int:
    """Convert a time object to minutes since midnight."""
    return value.hour * 60 + value.minute


@dataclass(frozen=True, kw_only=True)
class TRMNLTimeEntityDescription(TimeEntityDescription):
    """Describes a TRMNL time entity."""

    value_fn: Callable[[Device], time]
    set_value_fn: Callable[[TRMNLCoordinator, int, time], Coroutine[Any, Any, None]]


TIME_DESCRIPTIONS: tuple[TRMNLTimeEntityDescription, ...] = (
    TRMNLTimeEntityDescription(
        key="sleep_start_time",
        translation_key="sleep_start_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: _minutes_to_time(device.sleep_start_time),
        set_value_fn=lambda coordinator, device_id, value: (
            coordinator.client.update_device(
                device_id, sleep_start_time=_time_to_minutes(value)
            )
        ),
    ),
    TRMNLTimeEntityDescription(
        key="sleep_end_time",
        translation_key="sleep_end_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: _minutes_to_time(device.sleep_end_time),
        set_value_fn=lambda coordinator, device_id, value: (
            coordinator.client.update_device(
                device_id, sleep_end_time=_time_to_minutes(value)
            )
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TRMNLConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TRMNL time entities based on a config entry."""
    coordinator = entry.runtime_data

    known_device_ids: set[int] = set()

    def _async_entity_listener() -> None:
        new_ids = set(coordinator.data) - known_device_ids
        if new_ids:
            async_add_entities(
                TRMNLTimeEntity(coordinator, device_id, description)
                for device_id in new_ids
                for description in TIME_DESCRIPTIONS
            )
            known_device_ids.update(new_ids)

    entry.async_on_unload(coordinator.async_add_listener(_async_entity_listener))
    _async_entity_listener()


class TRMNLTimeEntity(TRMNLEntity, TimeEntity):
    """Defines a TRMNL time entity."""

    entity_description: TRMNLTimeEntityDescription

    def __init__(
        self,
        coordinator: TRMNLCoordinator,
        device_id: int,
        description: TRMNLTimeEntityDescription,
    ) -> None:
        """Initialize TRMNL time entity."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def native_value(self) -> time:
        """Return the current time value."""
        return self.entity_description.value_fn(self._device)

    @exception_handler
    async def async_set_value(self, value: time) -> None:
        """Set the time value."""
        await self.entity_description.set_value_fn(
            self.coordinator, self._device_id, value
        )
        await self.coordinator.async_request_refresh()
