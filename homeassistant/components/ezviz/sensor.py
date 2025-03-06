"""Support for EZVIZ sensors."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EzvizConfigEntry, EzvizDataUpdateCoordinator
from .entity import EzvizEntity

PARALLEL_UPDATES = 1

SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    "battery_level": SensorEntityDescription(
        key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
    ),
    "alarm_sound_mod": SensorEntityDescription(
        key="alarm_sound_mod",
        translation_key="alarm_sound_mod",
        entity_registry_enabled_default=False,
    ),
    "last_alarm_time": SensorEntityDescription(
        key="last_alarm_time",
        translation_key="last_alarm_time",
        entity_registry_enabled_default=False,
    ),
    "Seconds_Last_Trigger": SensorEntityDescription(
        key="Seconds_Last_Trigger",
        translation_key="seconds_last_trigger",
        entity_registry_enabled_default=False,
    ),
    "last_alarm_pic": SensorEntityDescription(
        key="last_alarm_pic",
        translation_key="last_alarm_pic",
        entity_registry_enabled_default=False,
    ),
    "supported_channels": SensorEntityDescription(
        key="supported_channels",
        translation_key="supported_channels",
    ),
    "local_ip": SensorEntityDescription(
        key="local_ip",
        translation_key="local_ip",
    ),
    "wan_ip": SensorEntityDescription(
        key="wan_ip",
        translation_key="wan_ip",
    ),
    "PIR_Status": SensorEntityDescription(
        key="PIR_Status",
        translation_key="pir_status",
    ),
    "last_alarm_type_code": SensorEntityDescription(
        key="last_alarm_type_code",
        translation_key="last_alarm_type_code",
    ),
    "last_alarm_type_name": SensorEntityDescription(
        key="last_alarm_type_name",
        translation_key="last_alarm_type_name",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EzvizConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up EZVIZ sensors based on a config entry."""
    coordinator = entry.runtime_data

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
    """Representation of a EZVIZ sensor."""

    def __init__(
        self, coordinator: EzvizDataUpdateCoordinator, serial: str, sensor: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial)
        self._sensor_name = sensor
        self._attr_unique_id = f"{serial}_{self._camera_name}.{sensor}"
        self.entity_description = SENSOR_TYPES[sensor]

    @property
    def native_value(self) -> int | str:
        """Return the state of the sensor."""
        return self.data[self._sensor_name]
