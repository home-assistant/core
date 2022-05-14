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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import Coordinator, async_setup_entry_platform


@dataclass
class EntityDescription(BinarySensorEntityDescription):
    """Entity description."""

    is_on: Callable = lambda _: False


SENSORS = (
    EntityDescription(
        key="grease-filter",
        name="Grease Filter",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on=lambda state: state.grease_filter_full,
    ),
    EntityDescription(
        key="carbon-filter",
        name="Carbon Filter",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on=lambda state: state.carbon_filter_full,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors dynamically through discovery."""

    def _constructor(coordinator: Coordinator) -> list[Entity]:
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


class BinarySensor(CoordinatorEntity[Coordinator], BinarySensorEntity):
    """Grease filter sensor."""

    entity_description: EntityDescription

    def __init__(
        self,
        coordinator: Coordinator,
        device: Device,
        device_info: DeviceInfo,
        entity_description: EntityDescription,
    ) -> None:
        """Init sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        self._attr_unique_id = f"{device.address}-{entity_description.key}"
        self._attr_device_info = device_info
        self._attr_name = f"{device_info['name']} {entity_description.name}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if data := self.coordinator.data:
            return self.entity_description.is_on(data)
        return None
