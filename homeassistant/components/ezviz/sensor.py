"""Support for Ezviz sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import DEVICE_CLASS_MOTION
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_BATTERY, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import EzvizDataUpdateCoordinator
from .entity import EzvizEntity

PARALLEL_UPDATES = 1

SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    "sw_version": SensorEntityDescription(key="sw_version"),
    "battery_level": SensorEntityDescription(
        key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_BATTERY,
    ),
    "alarm_sound_mod": SensorEntityDescription(key="alarm_sound_mod"),
    "detection_sensibility": SensorEntityDescription(key="detection_sensibility"),
    "last_alarm_time": SensorEntityDescription(key="last_alarm_time"),
    "Seconds_Last_Trigger": SensorEntityDescription(
        key="Seconds_Last_Trigger",
        entity_registry_enabled_default=False,
    ),
    "last_alarm_pic": SensorEntityDescription(key="last_alarm_pic"),
    "supported_channels": SensorEntityDescription(key="supported_channels"),
    "local_ip": SensorEntityDescription(key="local_ip"),
    "wan_ip": SensorEntityDescription(key="wan_ip"),
    "PIR_Status": SensorEntityDescription(
        key="PIR_Status",
        device_class=DEVICE_CLASS_MOTION,
    ),
    "last_alarm_type_code": SensorEntityDescription(key="last_alarm_type_code"),
    "last_alarm_type_name": SensorEntityDescription(key="last_alarm_type_name"),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ezviz sensors based on a config entry."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    async_add_entities(
        [
            EzvizSensor(coordinator, camera, sensor)
            for camera in coordinator.data
            for sensor, value in coordinator.data[camera].items()
            if sensor in SENSOR_TYPES
            if value is not None
        ]
    )


class EzvizSensor(EzvizEntity, SensorEntity):
    """Representation of a Ezviz sensor."""

    coordinator: EzvizDataUpdateCoordinator

    def __init__(
        self, coordinator: EzvizDataUpdateCoordinator, serial: str, sensor: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial)
        self._sensor_name = sensor
        self._attr_name = f"{self._camera_name} {sensor.title()}"
        self._attr_unique_id = f"{serial}_{self._camera_name}.{sensor}"
        self.entity_description = SENSOR_TYPES[sensor]

    @property
    def native_value(self) -> int | str:
        """Return the state of the sensor."""
        return self.data[self._sensor_name]
