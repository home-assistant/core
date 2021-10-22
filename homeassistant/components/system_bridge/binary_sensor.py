"""Support for System Bridge binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from systembridge import Bridge

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_UPDATE,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import SystemBridgeDeviceEntity
from .const import DOMAIN
from .coordinator import SystemBridgeDataUpdateCoordinator


@dataclass
class SystemBridgeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing System Bridge binary sensor entities."""

    value: Callable = round


BASE_BINARY_SENSOR_TYPES: tuple[SystemBridgeBinarySensorEntityDescription, ...] = (
    SystemBridgeBinarySensorEntityDescription(
        key="version_available",
        name="New Version Available",
        device_class=DEVICE_CLASS_UPDATE,
        value=lambda bridge: bridge.information.updates.available,
    ),
)

BATTERY_BINARY_SENSOR_TYPES: tuple[SystemBridgeBinarySensorEntityDescription, ...] = (
    SystemBridgeBinarySensorEntityDescription(
        key="battery_is_charging",
        name="Battery Is Charging",
        device_class=DEVICE_CLASS_BATTERY_CHARGING,
        value=lambda bridge: bridge.information.updates.available,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up System Bridge binary sensor based on a config entry."""
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    bridge: Bridge = coordinator.data

    entities = []
    for description in BASE_BINARY_SENSOR_TYPES:
        entities.append(SystemBridgeBinarySensor(coordinator, description))

    if bridge.battery and bridge.battery.hasBattery:
        for description in BATTERY_BINARY_SENSOR_TYPES:
            entities.append(SystemBridgeBinarySensor(coordinator, description))

    async_add_entities(entities)


class SystemBridgeBinarySensor(SystemBridgeDeviceEntity, BinarySensorEntity):
    """Define a System Bridge binary sensor."""

    coordinator: SystemBridgeDataUpdateCoordinator
    entity_description: SystemBridgeBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        description: SystemBridgeBinarySensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            description.key,
            description.name,
        )
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the boolean state of the binary sensor."""
        bridge: Bridge = self.coordinator.data
        return self.entity_description.value(bridge)
