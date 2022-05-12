"""Support for Canary sensors."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Final, cast

from canary.model import Device, Location, SensorType

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DATA_COORDINATOR,
    DATA_TYPE_ENTRY,
    DATA_TYPE_LOCATIONS,
    DATA_TYPE_READING,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import CanaryDataUpdateCoordinator
from .model import SensorTypeItem

SENSOR_VALUE_PRECISION: Final = 2
ATTR_AIR_QUALITY: Final = "air_quality"

# Define variables to store the device names, as referred to by the Canary API.
# Note: If Canary change's a name of a device (which they have done),
# then these variables will need updating, otherwise the sensors will stop working
# and disappear in Home Assistant.
CANARY_PRO: Final = "Canary Pro"
CANARY_FLEX: Final = "Canary Flex"
CANARY_VIEW: Final = "Canary View"

# Sensor types are defined like so:
# sensor type name, unit_of_measurement, icon, device class, products supported
SENSOR_TYPES: Final[list[SensorTypeItem]] = [
    (
        SensorType.TEMPERATURE,
        TEMP_CELSIUS,
        None,
        SensorDeviceClass.TEMPERATURE,
        [CANARY_PRO],
        DATA_TYPE_READING,
    ),
    (
        SensorType.HUMIDITY,
        PERCENTAGE,
        None,
        SensorDeviceClass.HUMIDITY,
        [CANARY_PRO],
        DATA_TYPE_READING,
    ),
    (
        SensorType.AIR_QUALITY,
        None,
        "weather-windy",
        None,
        [CANARY_PRO],
        DATA_TYPE_READING,
    ),
    (
        SensorType.WIFI,
        SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        None,
        SensorDeviceClass.SIGNAL_STRENGTH,
        [CANARY_PRO, CANARY_FLEX, CANARY_VIEW],
        DATA_TYPE_READING,
    ),
    (
        SensorType.BATTERY,
        PERCENTAGE,
        None,
        SensorDeviceClass.BATTERY,
        [CANARY_FLEX],
        DATA_TYPE_READING,
    ),
    (
        SensorType.DATE_LAST_ENTRY,
        None,
        "run-fast",
        SensorDeviceClass.TIMESTAMP,
        [CANARY_PRO, CANARY_FLEX],
        DATA_TYPE_ENTRY,
    ),
    (
        SensorType.ENTRIES_CAPTURED_TODAY,
        None,
        "file-video",
        None,
        [CANARY_PRO, CANARY_FLEX, CANARY_VIEW],
        DATA_TYPE_ENTRY,
    ),
]

STATE_AIR_QUALITY_NORMAL: Final = "normal"
STATE_AIR_QUALITY_ABNORMAL: Final = "abnormal"
STATE_AIR_QUALITY_VERY_ABNORMAL: Final = "very_abnormal"

_LOGGER = logging.getLogger(__name__)


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

    for location in coordinator.data[DATA_TYPE_LOCATIONS].values():
        for device in location.devices:
            if device.is_online:
                device_type = device.device_type
                for sensor_type in SENSOR_TYPES:
                    if device_type.get("name") in sensor_type[4]:
                        sensors.append(
                            CanarySensor(coordinator, sensor_type, location, device)
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

        sensor_type_name = sensor_type[0].value.replace("_", " ").title()
        self._attr_name = f"{location.name} {device.name} {sensor_type_name}"
        self._canary_type = self._sensor_type[0]
        self._canary_data_type = self._sensor_type[5]
        self._attr_unique_id = f"{device.device_id}_{sensor_type[0].value}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.device_id))},
            model=device.device_type["name"],
            manufacturer=MANUFACTURER,
            name=device.name,
        )
        self._attr_native_unit_of_measurement = sensor_type[1]
        self._attr_device_class = sensor_type[3]
        self._attr_icon = None if sensor_type[2] is None else f"mdi:{sensor_type[2]}"
        _LOGGER.info("CanarySensor: %s created", self._attr_name)

    @property
    def reading(self) -> float | None:
        """Return the device sensor reading."""
        try:
            readings = self.coordinator.data[DATA_TYPE_READING][self._device_id]
        except KeyError:
            return None

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
    def entry(self) -> str | datetime | int | None:
        """Return the state of the entry sensor."""
        try:
            entry = self.coordinator.data[DATA_TYPE_ENTRY][self._device_id]
        except KeyError:
            return None

        if entry is not None:
            if self._sensor_type[0] == SensorType.ENTRIES_CAPTURED_TODAY:
                return len(entry)
            if self._sensor_type[0] == SensorType.DATE_LAST_ENTRY:
                try:
                    last_entry_date = entry[0].start_time
                    return cast(datetime, last_entry_date)
                except IndexError:
                    return None
        return None

    @property
    def native_value(self) -> float | str | datetime | int | None:
        """Return the state of the sensor."""
        if self._canary_data_type == DATA_TYPE_READING:
            return self.reading
        if self._canary_data_type == DATA_TYPE_ENTRY:
            return self.entry
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes."""
        reading = self.reading

        if self._sensor_type[0] == SensorType.AIR_QUALITY.value and reading is not None:
            air_quality = None
            if reading <= 0.4:
                air_quality = STATE_AIR_QUALITY_VERY_ABNORMAL
            elif reading <= 0.59:
                air_quality = STATE_AIR_QUALITY_ABNORMAL
            else:
                air_quality = STATE_AIR_QUALITY_NORMAL

            return {ATTR_AIR_QUALITY: air_quality}

        return None
