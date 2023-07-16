"""Support for System Bridge binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SystemBridgeEntity
from .const import DOMAIN
from .coordinator import SystemBridgeDataUpdateCoordinator


@dataclass
class SystemBridgeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing System Bridge binary sensor entities."""

    # SystemBridgeBinarySensor does not support UNDEFINED or None,
    # restrict the type to str.
    name: str = ""

    value: Callable = round


BASE_BINARY_SENSOR_TYPES: tuple[SystemBridgeBinarySensorEntityDescription, ...] = (
    SystemBridgeBinarySensorEntityDescription(
        key="version_available",
        name="New version available",
        device_class=BinarySensorDeviceClass.UPDATE,
        value=lambda data: data.system.version_newer_available,
    ),
)

BATTERY_BINARY_SENSOR_TYPES: tuple[SystemBridgeBinarySensorEntityDescription, ...] = (
    SystemBridgeBinarySensorEntityDescription(
        key="battery_is_charging",
        name="Battery is charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value=lambda data: data.battery.is_charging,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up System Bridge binary sensor based on a config entry."""
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for description in BASE_BINARY_SENSOR_TYPES:
        entities.append(
            SystemBridgeBinarySensor(coordinator, description, entry.data[CONF_PORT])
        )

    if (
        coordinator.data.battery
        and coordinator.data.battery.percentage
        and coordinator.data.battery.percentage > -1
    ):
        for description in BATTERY_BINARY_SENSOR_TYPES:
            entities.append(
                SystemBridgeBinarySensor(
                    coordinator, description, entry.data[CONF_PORT]
                )
            )

    async_add_entities(entities)


class SystemBridgeBinarySensor(SystemBridgeEntity, BinarySensorEntity):
    """Define a System Bridge binary sensor."""

    entity_description: SystemBridgeBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        description: SystemBridgeBinarySensorEntityDescription,
        api_port: int,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            api_port,
            description.key,
            description.name,
        )
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the boolean state of the binary sensor."""
        return self.entity_description.value(self.coordinator.data)
