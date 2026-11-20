"""PTDevices Binary Sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import PTDevicesConfigEntry, PTDevicesCoordinator
from .entity import PTDevicesEntity

PARALLEL_UPDATES = 0


class PTDevicesBinarySensors(StrEnum):
    """Store keys for PTDevices binary sensors."""

    DEVICE_BATTERY_STATUS = "battery_status"
    DEVICE_EXTERNAL_POWER = "external_power"


@dataclass(kw_only=True, frozen=True)
class PTDevicesBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Description for PTDevices binary sensor entities."""

    is_on_fn: Callable[[dict[str, StateType]], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[PTDevicesBinarySensorEntityDescription, ...] = (
    PTDevicesBinarySensorEntityDescription(
        key=PTDevicesBinarySensors.DEVICE_BATTERY_STATUS,
        translation_key=PTDevicesBinarySensors.DEVICE_BATTERY_STATUS,
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: (
            None
            if data.get(PTDevicesBinarySensors.DEVICE_BATTERY_STATUS)
            in (None, "unknown")
            else data.get(PTDevicesBinarySensors.DEVICE_BATTERY_STATUS) == "low"
        ),
    ),
    PTDevicesBinarySensorEntityDescription(
        key=PTDevicesBinarySensors.DEVICE_EXTERNAL_POWER,
        translation_key=PTDevicesBinarySensors.DEVICE_EXTERNAL_POWER,
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: (
            bool(data.get(PTDevicesBinarySensors.DEVICE_EXTERNAL_POWER))
            if data.get(PTDevicesBinarySensors.DEVICE_EXTERNAL_POWER) is not None
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PTDevicesConfigEntry,
    async_add_entity: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup PTDevices binary sensors based on config entry."""
    coordinator = config_entry.runtime_data

    known_sensors: set[tuple[str, str]] = set()

    def _check_device() -> None:
        for device_id in sorted(coordinator.data):
            device = coordinator.data[device_id]
            new_sensors = [
                sensor
                for sensor in BINARY_SENSOR_DESCRIPTIONS
                if sensor.key in device and (device_id, sensor.key) not in known_sensors
            ]
            if not new_sensors:
                continue
            known_sensors.update((device_id, sensor.key) for sensor in new_sensors)
            async_add_entity(
                PTDevicesBinarySensorEntity(
                    config_entry.runtime_data, sensor, device_id
                )
                for sensor in new_sensors
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
            coordinator,
            description.key,
            device_id,
        )

        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        return self.entity_description.is_on_fn(self.device)
