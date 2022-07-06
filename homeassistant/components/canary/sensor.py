"""Support for Canary sensors."""
from __future__ import annotations

from typing import Final, Optional

from canary.model import Device, Location, SensorType

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN, MANUFACTURER
from .coordinator import CanaryDataUpdateCoordinator

SensorTypeItem = tuple[
    str, Optional[str], Optional[str], Optional[SensorDeviceClass], list[str]
]

SENSOR_VALUE_PRECISION: Final = 2
ATTR_AIR_QUALITY: Final = "air_quality"

# Define variables to store the device names, as referred to by the Canary API.
# Note: If Canary changes the name of their devices (which they have done),
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
        [CANARY_PRO, CANARY_FLEX],
    ),
    ("battery", PERCENTAGE, None, SensorDeviceClass.BATTERY, [CANARY_FLEX]),
    ("last_entry_date", None, "mdi:run-fast", None, [CANARY_PRO, CANARY_FLEX]),
    ("entries_captured_today", None, "mdi:file-video", None, [CANARY_PRO, CANARY_FLEX]),
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
        self._canary_data_type = "readings"
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
        elif self._sensor_type[0] == "last_entry_date":
            canary_sensor_type = SensorType.DATE_LAST_ENTRY
            self._canary_data_type = "entries"
        elif self._sensor_type[0] == "entries_captured_today":
            canary_sensor_type = SensorType.ENTRIES_CAPTURED_TODAY
            self._canary_data_type = "entries"

        self._canary_type = canary_sensor_type
        self._attr_unique_id = f"{device.device_id}_{sensor_type[0]}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.device_id))},
            model=device.device_type["name"],
            manufacturer=MANUFACTURER,
            name=device.name,
        )
        self._attr_native_unit_of_measurement = sensor_type[1]
        self._state: str | int | float | datetime | None = None
        self._attr_icon = sensor_type[2]
        _LOGGER.debug("%s initialized", self.name)

    @property
    def device_class(self) -> str | None:
        """Return the device class of the sensor."""
        if self._canary_type == SensorType.TEMPERATURE:
            return SensorDeviceClass.TEMPERATURE
        if self._canary_type == SensorType.HUMIDITY:
            return SensorDeviceClass.HUMIDITY
        if self._canary_type == SensorType.WIFI:
            return SensorDeviceClass.SIGNAL_STRENGTH
        if self._canary_type == SensorType.BATTERY:
            return SensorDeviceClass.BATTERY
        if self._canary_type == SensorType.DATE_LAST_ENTRY:
            return SensorDeviceClass.TIMESTAMP
        return None

    @property
    def name(self) -> str:
        """Name of sensor."""
        return str(self._attr_name)

    # @property
    def reading(self) -> None:
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

        self._state = (
            None if value is None else round(float(value), SENSOR_VALUE_PRECISION)
        )

    # @property
    def entry(self) -> None:
        """Return the state of the entry sensor."""
        entry = self.coordinator.data["entries"][self._device_id]

        if entry is not None:
            if self._canary_type == SensorType.ENTRIES_CAPTURED_TODAY:
                self._state = len(entry)
            if self._canary_type == SensorType.DATE_LAST_ENTRY:
                try:
                    last_entry_date = entry[0].start_time
                    self._state = cast(datetime, last_entry_date)
                except IndexError:
                    self._state = None

    @property
    def native_value(self) -> float | str | datetime | int | None:
        """Return the state of the sensor."""
        if self._canary_data_type == "readings":
            self.reading()
        if self._canary_data_type == "entries":
            self.entry()
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes."""
        if self._canary_type == SensorType.AIR_QUALITY and self._state is not None:
            self._state = float(str(self._state))
            if self._state <= 0.4:
                air_quality = STATE_AIR_QUALITY_VERY_ABNORMAL
            elif self._state <= 0.59:
                air_quality = STATE_AIR_QUALITY_ABNORMAL
            else:
                air_quality = STATE_AIR_QUALITY_NORMAL

            return {ATTR_AIR_QUALITY: air_quality}

        return None
