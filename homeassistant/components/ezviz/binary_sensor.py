"""Support for EZVIZ binary sensors."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .contact_device_class import (
    async_ensure_contact_window_i18n,
    infer_contact_sensor_device_class,
)
from .coordinator import EzvizConfigEntry, EzvizDataUpdateCoordinator
from .entity import EzvizEntity

_LOGGER = logging.getLogger(__name__)

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
    # device_class overridden per entity from device name (see EzvizBinarySensor.device_class).
    "door_status": BinarySensorEntityDescription(
        key="door_status",
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    "water_leak_status": BinarySensorEntityDescription(
        key="water_leak_status",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EzvizConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up EZVIZ sensors based on a config entry."""
    await async_ensure_contact_window_i18n(hass)
    coordinator = entry.runtime_data

    _LOGGER.debug(
        "binary_sensor setup: %d devices in coordinator.data, keys per device:",
        len(coordinator.data),
    )
    for camera in coordinator.data:
        matching = {
            k: v for k, v in coordinator.data[camera].items()
            if k in BINARY_SENSOR_TYPES
        }
        _LOGGER.debug(
            "  %s (%s): matching keys=%s",
            camera,
            coordinator.data[camera].get("device_category"),
            {k: v for k, v in matching.items()},
        )

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
        if binary_sensor == "door_status":
            _LOGGER.debug(
                "door_status device %s: inferred device_class=%s from name=%r",
                serial,
                infer_contact_sensor_device_class(
                    coordinator.hass, self.data.get("name")
                ),
                self.data.get("name"),
            )

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Use WINDOW when the EZVIZ device name suggests a window contact."""
        if self._sensor_name == "door_status":
            return infer_contact_sensor_device_class(
                self.coordinator.hass, self.data.get("name")
            )
        return self.entity_description.device_class

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        value = self.data[self._sensor_name]
        if self._sensor_name == "water_leak_status":
            return value != 2
        return bool(value)
