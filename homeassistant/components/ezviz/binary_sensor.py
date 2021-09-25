"""Support for Ezviz binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
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
        key="Motion_Trigger", device_class=DEVICE_CLASS_MOTION
    ),
    "alarm_schedules_enabled": BinarySensorEntityDescription(
        key="alarm_schedules_enabled"
    ),
    "encrypted": BinarySensorEntityDescription(key="encrypted"),
    "upgrade_available": BinarySensorEntityDescription(key="upgrade_available"),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ezviz sensors based on a config entry."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    sensors = []

    for idx, camera in enumerate(coordinator.data):
        for binary_sensor in camera:
            # Only add sensor with value.
            if camera.get(binary_sensor) is None:
                continue

            if binary_sensor in BINARY_SENSOR_TYPES:
                sensors.append(EzvizBinarySensor(coordinator, idx, binary_sensor))

    async_add_entities(sensors)


class EzvizBinarySensor(EzvizEntity, BinarySensorEntity):
    """Representation of a Ezviz sensor."""

    coordinator: EzvizDataUpdateCoordinator

    def __init__(
        self,
        coordinator: EzvizDataUpdateCoordinator,
        idx: int,
        binary_sensor: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, idx)
        self._sensor_name = binary_sensor
        self._attr_name = f"{self._camera_name} {binary_sensor.title()}"
        self._attr_unique_id = f"{self._serial}_{self._camera_name}.{binary_sensor}"
        self.entity_description = BINARY_SENSOR_TYPES[binary_sensor]

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.data[self._sensor_name]
