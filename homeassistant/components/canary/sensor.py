"""Support for Canary sensors."""

from __future__ import annotations

from typing import Final

from canary.model import Device, Location, SensorType

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import CanaryConfigEntry, CanaryDataUpdateCoordinator

type SensorTypeItem = tuple[
    str, str | None, str | None, SensorDeviceClass | None, list[str]
]

SENSOR_VALUE_PRECISION: Final = 2
ATTR_AIR_QUALITY: Final = "air_quality"

# Define variables to store the device names, as referred to by the Canary API.
# Note: If Canary change the name of any of their devices (which they have done),
# then these variables will need updating, otherwise the sensors will stop working
# and disappear in Home Assistant.
CANARY_PRO: Final = "Canary Pro"
CANARY_FLEX: Final = "Canary Flex"

# Sensor types are defined like so:
# sensor type name, unit_of_measurement, icon, device class, products supported
SENSOR_TYPES: Final[list[SensorTypeItem]] = [
    (
        "temperature",
        UnitOfTemperature.CELSIUS,
        None,
        SensorDeviceClass.TEMPERATURE,
        [CANARY_PRO],
    ),
    ("humidity", PERCENTAGE, None, SensorDeviceClass.HUMIDITY, [CANARY_PRO]),
    ("air_quality", None, "mdi:weather-windy", None, [CANARY_PRO]),
    (
        "wifi",
        SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        None,
        SensorDeviceClass.SIGNAL_STRENGTH,
        [CANARY_FLEX],
    ),
    ("battery", PERCENTAGE, None, SensorDeviceClass.BATTERY, [CANARY_FLEX]),
]

STATE_AIR_QUALITY_NORMAL: Final = "normal"
STATE_AIR_QUALITY_ABNORMAL: Final = "abnormal"
STATE_AIR_QUALITY_VERY_ABNORMAL: Final = "very_abnormal"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CanaryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Canary sensors based on a config entry."""
    coordinator = entry.runtime_data
    sensors: list[CanarySensor] = []

    for location in coordinator.data["locations"].values():
        for device in location.devices:
            if device.is_online:
                device_type = device.device_type
                sensors.extend(
                    CanarySensor(coordinator, sensor_type, location, device)
                    for sensor_type in SENSOR_TYPES
                    if device_type.get("name") in sensor_type[4]
                )

    async_add_entities(sensors, True)


class CanarySensor(CoordinatorEntity[CanaryDataUpdateCoordinator], SensorEntity):
    """Representation of a Canary sensor."""

    def __init__(
        self,
        coordinator: CanaryDataUpdateCoordinator,
        sensor_type: SensorTypeItem,
        location: Location,
        device: Device,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._device_id = device.device_id

        sensor_type_name = sensor_type[0].replace("_", " ").title()
        self._attr_name = f"{location.name} {device.name} {sensor_type_name}"

        canary_sensor_type = None
        if self._sensor_type[0] == "air_quality":
            canary_sensor_type = SensorType.AIR_QUALITY
        elif self._sensor_type[0] == "temperature":
            canary_sensor_type = SensorType.TEMPERATURE
        elif self._sensor_type[0] == "humidity":
            canary_sensor_type = SensorType.HUMIDITY
        elif self._sensor_type[0] == "wifi":
            canary_sensor_type = SensorType.WIFI
        elif self._sensor_type[0] == "battery":
            canary_sensor_type = SensorType.BATTERY

        self._canary_type = canary_sensor_type
        self._attr_unique_id = f"{device.device_id}_{sensor_type[0]}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.device_id))},
            model=device.device_type["name"],
            manufacturer=MANUFACTURER,
            name=device.name,
        )
        self._attr_native_unit_of_measurement = sensor_type[1]
        self._attr_device_class = sensor_type[3]
        self._attr_icon = sensor_type[2]

    @property
    def reading(self) -> float | None:
        """Return the device sensor reading."""
        readings = self.coordinator.data["readings"][self._device_id]

        value = next(
            (
                reading.value
                for reading in readings
                if reading.sensor_type == self._canary_type
            ),
            None,
        )

        if value is not None:
            return round(float(value), SENSOR_VALUE_PRECISION)

        return None

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.reading

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes."""
        reading = self.reading

        if self._sensor_type[0] == "air_quality" and reading is not None:
            air_quality = None
            if reading <= 0.4:
                air_quality = STATE_AIR_QUALITY_VERY_ABNORMAL
            elif reading <= 0.59:
                air_quality = STATE_AIR_QUALITY_ABNORMAL
            else:
                air_quality = STATE_AIR_QUALITY_NORMAL

            return {ATTR_AIR_QUALITY: air_quality}

        return None
