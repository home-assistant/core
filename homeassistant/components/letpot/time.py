"""Support for LetPot time entities."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import time
from typing import Any

from letpot.deviceclient import LetPotDeviceClient
from letpot.models import LetPotDeviceStatus

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LetPotConfigEntry
from .coordinator import LetPotDeviceCoordinator
from .entity import LetPotEntity

# Each change pushes a 'full' device status with the change. The library will cache
# pending changes to avoid overwriting, but try to avoid a lot of parallelism.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class LetPotTimeEntityDescription(TimeEntityDescription):
    """Describes a LetPot time entity."""

    value_fn: Callable[[LetPotDeviceStatus], time | None]
    set_value_fn: Callable[[LetPotDeviceClient, time], Coroutine[Any, Any, None]]


TIME_SENSORS: tuple[LetPotTimeEntityDescription, ...] = (
    LetPotTimeEntityDescription(
        key="light_schedule_end",
        translation_key="light_schedule_end",
        value_fn=lambda status: None if status is None else status.light_schedule_end,
        set_value_fn=lambda deviceclient, value: deviceclient.set_light_schedule(
            start=None, end=value
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    LetPotTimeEntityDescription(
        key="light_schedule_start",
        translation_key="light_schedule_start",
        value_fn=lambda status: None if status is None else status.light_schedule_start,
        set_value_fn=lambda deviceclient, value: deviceclient.set_light_schedule(
            start=value, end=None
        ),
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LetPotConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LetPot time entities based on a config entry."""
    coordinators = entry.runtime_data
    async_add_entities(
        LetPotTimeEntity(coordinator, description)
        for description in TIME_SENSORS
        for coordinator in coordinators
    )


class LetPotTimeEntity(LetPotEntity, TimeEntity):
    """Defines a LetPot time entity."""

    entity_description: LetPotTimeEntityDescription

    def __init__(
        self,
        coordinator: LetPotDeviceCoordinator,
        description: LetPotTimeEntityDescription,
    ) -> None:
        """Initialize LetPot time entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{coordinator.device.serial_number}_{description.key}"

    @property
    def native_value(self) -> time | None:
        """Return the time."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_set_value(self, value: time) -> None:
        """Set the time."""
        await self.entity_description.set_value_fn(
            self.coordinator.device_client, value
        )
