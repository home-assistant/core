"""Support for Canary sensors."""
from __future__ import annotations

from typing import Final

from canary.api import Device, Location, SensorType

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN, MANUFACTURER
from .coordinator import CanaryDataUpdateCoordinator
from .model import SensorTypeItem

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
    ("temperature", TEMP_CELSIUS, None, DEVICE_CLASS_TEMPERATURE, [CANARY_PRO]),
    ("humidity", PERCENTAGE, None, DEVICE_CLASS_HUMIDITY, [CANARY_PRO]),
    ("air_quality", None, "mdi:weather-windy", None, [CANARY_PRO]),
    (
        "wifi",
        SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        None,
        DEVICE_CLASS_SIGNAL_STRENGTH,
        [CANARY_FLEX],
    ),
    ("battery", PERCENTAGE, None, DEVICE_CLASS_BATTERY, [CANARY_FLEX]),
]

STATE_AIR_QUALITY_NORMAL: Final = "normal"
STATE_AIR_QUALITY_ABNORMAL: Final = "abnormal"
STATE_AIR_QUALITY_VERY_ABNORMAL: Final = "very_abnormal"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Canary sensors based on a config entry."""
    coordinator: CanaryDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    sensors: list[CanarySensor] = []

    for location in coordinator.data["locations"].values():
        for device in location.devices:
            if device.is_online:
                device_type = device.device_type
                for sensor_type in SENSOR_TYPES:
                    if device_type.get("name") in sensor_type[4]:
                        sensors.append(
                            CanarySensor(coordinator, sensor_type, location, device)
                        )

    async_add_entities(sensors, True)


class CanarySensor(CoordinatorEntity, SensorEntity):
    """Representation of a Canary sensor."""

    coordinator: CanaryDataUpdateCoordinator

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
        self._device_name = device.name
        self._device_type_name = device.device_type["name"]

        sensor_type_name = sensor_type[0].replace("_", " ").title()
        self._name = f"{location.name} {device.name} {sensor_type_name}"

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
    def name(self) -> str:
        """Return the name of the Canary sensor."""
        return self._name

    @property
    def state(self) -> float | None:
        """Return the state of the sensor."""
        return self.reading

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this sensor."""
        return f"{self._device_id}_{self._sensor_type[0]}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, str(self._device_id))},
            "name": self._device_name,
            "model": self._device_type_name,
            "manufacturer": MANUFACTURER,
        }

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self._sensor_type[1]

    @property
    def device_class(self) -> str | None:
        """Device class for the sensor."""
        return self._sensor_type[3]

    @property
    def icon(self) -> str | None:
        """Icon for the sensor."""
        return self._sensor_type[2]

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
