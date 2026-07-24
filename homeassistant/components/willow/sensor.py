"""Support for Willow sensors."""

from dataclasses import dataclass
from datetime import datetime
from typing import cast

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
from homeassistant.util import dt as dt_util

from . import WillowConfigEntry
from .const import DOMAIN, MANUFACTURER
from .coordinator import WillowDataUpdateCoordinator, WillowDevice

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class WillowSensorEntityDescription(SensorEntityDescription):
    """Describe a Willow sensor entity."""

    reading_key: str | None = None


SENSOR_DESCRIPTIONS: tuple[WillowSensorEntityDescription, ...] = (
    WillowSensorEntityDescription(
        key="battery_life",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="battery_life",
    ),
    WillowSensorEntityDescription(
        key="temperature",
        reading_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WillowSensorEntityDescription(
        key="humidity",
        reading_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WillowSensorEntityDescription(
        key="moisture",
        reading_key="moisture",
        device_class=SensorDeviceClass.MOISTURE,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WillowSensorEntityDescription(
        key="light",
        reading_key="light",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WillowSensorEntityDescription(
        key="timestamp",
        reading_key="timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="last_reading",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WillowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Willow sensor entities."""
    coordinator = entry.runtime_data.coordinator
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
        self._attr_device_info = self._device_info(device)

    @property
    def native_value(self) -> StateType | datetime:
        """Return the native value."""
        device = self.coordinator.data.get(self._sensor_id)
        if device is None:
            return None

        if self.entity_description.key == "battery_life":
            return device.get("battery_life")

        reading = device.get("latest_reading")
        if reading is None or self.entity_description.reading_key is None:
            return None

        value = cast(StateType, reading.get(self.entity_description.reading_key))
        if self.entity_description.device_class is SensorDeviceClass.TIMESTAMP:
            return dt_util.parse_datetime(value) if isinstance(value, str) else None

        return value

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.native_value is not None

    def _device_info(self, device: WillowDevice) -> DeviceInfo:
        """Return device information."""
        plant = device["user_plant"]
        info = DeviceInfo(
            identifiers={(DOMAIN, self._sensor_id)},
            manufacturer=MANUFACTURER,
            model="Willow Sensor",
            name=plant["name"],
        )

        if version := device.get("version"):
            info["sw_version"] = version

        if location := plant.get("location"):
            info["suggested_area"] = location

        return info
