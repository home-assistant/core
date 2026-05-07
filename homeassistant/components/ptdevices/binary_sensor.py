"""PTDevices Binary Sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

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
            data.get(PTDevicesBinarySensors.DEVICE_BATTERY_STATUS) == "low"
            if data.get(PTDevicesBinarySensors.DEVICE_BATTERY_STATUS)
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

    def _async_add_new_sensor(
        sensors: list[tuple[str, str]],
    ) -> None:
        """Add new sensors."""
        async_add_entity(
            PTDevicesBinarySensorEntity(config_entry.runtime_data, sensor, device_id)
            for device_id, sensor_key in sensors
            for sensor in BINARY_SENSOR_DESCRIPTIONS
            if sensor_key == sensor.key
        )

    coordinator.new_sensor_callbacks.append(_async_add_new_sensor)
    _async_add_new_sensor(
        [
            (device_id, sensor_key)
            for device_id, sensors in coordinator.data.items()
            for sensor_key in sensors
            if (device_id, sensor_key) in coordinator.known_sensors
        ]
    )


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
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        return self.entity_description.is_on_fn(self.device)
