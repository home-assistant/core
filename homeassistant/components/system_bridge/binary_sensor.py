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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import SystemBridgeDataUpdateCoordinator
from .data import SystemBridgeData
from .entity import SystemBridgeEntity


@dataclass(frozen=True)
class SystemBridgeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing System Bridge binary sensor entities."""

    value_fn: Callable = round


def camera_in_use(data: SystemBridgeData) -> bool | None:
    """Return if any camera is in use."""
    if data.system.camera_usage is not None:
        return len(data.system.camera_usage) > 0
    return None


BASE_BINARY_SENSOR_TYPES: tuple[SystemBridgeBinarySensorEntityDescription, ...] = (
    SystemBridgeBinarySensorEntityDescription(
        key="camera_in_use",
        translation_key="camera_in_use",
        icon="mdi:webcam",
        value_fn=camera_in_use,
    ),
    SystemBridgeBinarySensorEntityDescription(
        key="pending_reboot",
        translation_key="pending_reboot",
        icon="mdi:restart",
        value_fn=lambda data: data.system.pending_reboot,
    ),
    SystemBridgeBinarySensorEntityDescription(
        key="version_available",
        device_class=BinarySensorDeviceClass.UPDATE,
        value_fn=lambda data: data.system.version_newer_available,
    ),
)

BATTERY_BINARY_SENSOR_TYPES: tuple[SystemBridgeBinarySensorEntityDescription, ...] = (
    SystemBridgeBinarySensorEntityDescription(
        key="battery_is_charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda data: data.battery.is_charging,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up System Bridge binary sensor based on a config entry."""
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        SystemBridgeBinarySensor(coordinator, description, entry.data[CONF_PORT])
        for description in BASE_BINARY_SENSOR_TYPES
    ]

    if (
        coordinator.data.battery
        and coordinator.data.battery.percentage
        and coordinator.data.battery.percentage > -1
    ):
        entities.extend(
            SystemBridgeBinarySensor(coordinator, description, entry.data[CONF_PORT])
            for description in BATTERY_BINARY_SENSOR_TYPES
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
        )
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the boolean state of the binary sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
