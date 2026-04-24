"""Support for Fumis binary sensor entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fumis import FumisInfo

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FumisConfigEntry, FumisDataUpdateCoordinator
from .entity import FumisEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class FumisBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Fumis binary sensor entity."""

    has_fn: Callable[[FumisInfo], bool] = lambda _: True
    is_on_fn: Callable[[FumisInfo], bool | None]


BINARY_SENSORS: tuple[FumisBinarySensorEntityDescription, ...] = (
    FumisBinarySensorEntityDescription(
        key="door",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.controller.door_open is not None,
        is_on_fn=lambda data: data.controller.door_open,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FumisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fumis binary sensor entities based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        FumisBinarySensorEntity(coordinator=coordinator, description=description)
        for description in BINARY_SENSORS
        if description.has_fn(coordinator.data)
    )


class FumisBinarySensorEntity(FumisEntity, BinarySensorEntity):
    """Defines a Fumis binary sensor entity."""

    entity_description: FumisBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: FumisDataUpdateCoordinator,
        description: FumisBinarySensorEntityDescription,
    ) -> None:
        """Initialize the Fumis binary sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.is_on_fn(self.coordinator.data)
