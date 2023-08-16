"""Support for EZVIZ binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import EzvizDataUpdateCoordinator
from .entity import EzvizEntity

PARALLEL_UPDATES = 1

BINARY_SENSOR_TYPES: dict[str, BinarySensorEntityDescription] = {
    "Motion_Trigger": BinarySensorEntityDescription(
        key="Motion_Trigger",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    "alarm_schedules_enabled": BinarySensorEntityDescription(
        key="alarm_schedules_enabled",
        translation_key="alarm_schedules_enabled",
    ),
    "encrypted": BinarySensorEntityDescription(
        key="encrypted",
        translation_key="encrypted",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up EZVIZ sensors based on a config entry."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    async_add_entities(
        [
            EzvizBinarySensor(coordinator, camera, binary_sensor)
            for camera in coordinator.data
            for binary_sensor, value in coordinator.data[camera].items()
            if binary_sensor in BINARY_SENSOR_TYPES
            if value is not None
        ]
    )


class EzvizBinarySensor(EzvizEntity, BinarySensorEntity):
    """Representation of a EZVIZ sensor."""

    def __init__(
        self,
        coordinator: EzvizDataUpdateCoordinator,
        serial: str,
        binary_sensor: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial)
        self._sensor_name = binary_sensor
        self._attr_unique_id = f"{serial}_{self._camera_name}.{binary_sensor}"
        self.entity_description = BINARY_SENSOR_TYPES[binary_sensor]

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.data[self._sensor_name]
