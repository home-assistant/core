"""Support for sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fjaraskupan import Device

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import async_setup_entry_platform
from .coordinator import FjaraskupanConfigEntry, FjaraskupanCoordinator


@dataclass(frozen=True)
class EntityDescription(BinarySensorEntityDescription):
    """Entity description."""

    is_on: Callable = lambda _: False


SENSORS = (
    EntityDescription(
        key="grease-filter",
        translation_key="grease_filter",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on=lambda state: state.grease_filter_full,
    ),
    EntityDescription(
        key="carbon-filter",
        translation_key="carbon_filter",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on=lambda state: state.carbon_filter_full,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FjaraskupanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors dynamically through discovery."""

    def _constructor(coordinator: FjaraskupanCoordinator) -> list[Entity]:
        return [
            BinarySensor(
                coordinator,
                coordinator.device,
                coordinator.device_info,
                entity_description,
            )
            for entity_description in SENSORS
        ]

    async_setup_entry_platform(hass, config_entry, async_add_entities, _constructor)


class BinarySensor(CoordinatorEntity[FjaraskupanCoordinator], BinarySensorEntity):
    """Grease filter sensor."""

    entity_description: EntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FjaraskupanCoordinator,
        device: Device,
        device_info: DeviceInfo,
        entity_description: EntityDescription,
    ) -> None:
        """Init sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        self._attr_unique_id = f"{device.address}-{entity_description.key}"
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if data := self.coordinator.data:
            return self.entity_description.is_on(data)
        return None
