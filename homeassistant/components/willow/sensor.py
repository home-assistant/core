"""Support for Willow sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from pywillow import WillowDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import LIGHT_LUX, PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import WillowConfigEntry, WillowDataUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class WillowSensorEntityDescription(SensorEntityDescription):
    """Describe a Willow sensor entity."""

    value_fn: Callable[[WillowDevice], StateType]


SENSOR_DESCRIPTIONS: tuple[WillowSensorEntityDescription, ...] = (
    WillowSensorEntityDescription(
        key="battery_life",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device["battery_life"],
    ),
    WillowSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=(
            lambda device: (
                reading["temperature"]
                if (reading := device["latest_reading"])
                else None
            )
        ),
    ),
    WillowSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=(
            lambda device: (
                reading["humidity"] if (reading := device["latest_reading"]) else None
            )
        ),
    ),
    WillowSensorEntityDescription(
        key="moisture",
        device_class=SensorDeviceClass.MOISTURE,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=(
            lambda device: (
                reading["moisture"] if (reading := device["latest_reading"]) else None
            )
        ),
    ),
    WillowSensorEntityDescription(
        key="light",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=(
            lambda device: (
                reading["light"] if (reading := device["latest_reading"]) else None
            )
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WillowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Willow sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        WillowSensor(coordinator, device, description)
        for device in coordinator.data.values()
        for description in SENSOR_DESCRIPTIONS
    )


class WillowSensor(CoordinatorEntity[WillowDataUpdateCoordinator], SensorEntity):
    """Representation of a Willow sensor."""

    entity_description: WillowSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WillowDataUpdateCoordinator,
        device: WillowDevice,
        description: WillowSensorEntityDescription,
    ) -> None:
        """Initialize the Willow sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._sensor_id = str(device["sensor_id"])
        self._attr_unique_id = f"{self._sensor_id}_{description.key}"
        plant = device["user_plant"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._sensor_id)},
            manufacturer=MANUFACTURER,
            model="Willow Sensor",
            name=plant["name"],
            sw_version=device["version"],
            suggested_area=plant["location"],
        )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the native value."""
        return self.entity_description.value_fn(self.coordinator.data[self._sensor_id])

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._sensor_id in self.coordinator.data
