"""PTDevices Binary Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PTDevicesConfigEntry, PTDevicesCoordinator
from .entity import PTDevicesEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


class PTDevicesBinarySensors(StrEnum):
    """Store keys for PTDevices binary sensors."""

    DEVICE_BATTERY_STATUS = "battery_status"


@dataclass(kw_only=True, frozen=True)
class PTDevicesBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Description for PTDevices sensor entities."""

    is_on_fn: Callable[[dict[str, str | int | float | None]], bool]


BINARY_SENSOR_DESCRIPTIONS: tuple[PTDevicesBinarySensorEntityDescription, ...] = (
    PTDevicesBinarySensorEntityDescription(
        key=PTDevicesBinarySensors.DEVICE_BATTERY_STATUS,
        translation_key=PTDevicesBinarySensors.DEVICE_BATTERY_STATUS,
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data.get(PTDevicesBinarySensors.DEVICE_BATTERY_STATUS)
        == "low",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PTDevicesConfigEntry,
    async_add_entity: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup PTDevices binary sensors based on config entry."""
    coordinator = config_entry.runtime_data

    known_devices: set[str] = set()

    def _check_device() -> None:
        current_devices = set(coordinator.data.keys())
        new_devices = current_devices - known_devices
        if new_devices:
            known_devices.update(new_devices)
            for device_id in new_devices:
                device = coordinator.data[device_id]
                async_add_entity(
                    PTDevicesBinarySensorEntity(
                        config_entry.runtime_data,
                        sensor,
                        device_id,
                    )
                    for sensor in BINARY_SENSOR_DESCRIPTIONS
                    if sensor.key in device
                )

    _check_device()
    config_entry.async_on_unload(coordinator.async_add_listener(_check_device))


class PTDevicesBinarySensorEntity(PTDevicesEntity, BinarySensorEntity):
    """Defines a PTDevices binary sensor."""

    entity_description: PTDevicesBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: PTDevicesCoordinator,
        description: PTDevicesBinarySensorEntityDescription,
        device_id: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(
            coordinator=coordinator,
            sensor_key=description.key,
            device_id=device_id,
        )

        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the state of the senor."""
        return self.entity_description.is_on_fn(self.device)
