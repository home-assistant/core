"""Support for Blink system camera control."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_BRAND,
    DOMAIN,
    TYPE_BATTERY,
    TYPE_CAMERA_ARMED,
    TYPE_MOTION_DETECTED,
)

_LOGGER = logging.getLogger(__name__)

BINARY_SENSORS_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key=TYPE_BATTERY,
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key=TYPE_CAMERA_ARMED,
        translation_key="camera_armed",
    ),
    BinarySensorEntityDescription(
        key=TYPE_MOTION_DETECTED,
        device_class=BinarySensorDeviceClass.MOTION,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the blink binary sensors."""
    data = hass.data[DOMAIN][config.entry_id]

    entities = [
        BlinkBinarySensor(data, camera, description)
        for camera in data.cameras
        for description in BINARY_SENSORS_TYPES
    ]
    async_add_entities(entities)


class BlinkBinarySensor(BinarySensorEntity):
    """Representation of a Blink binary sensor."""

    _attr_has_entity_name = True

    def __init__(
        self, data, camera, description: BinarySensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        self.data = data
        self.entity_description = description
        self._camera = data.cameras[camera]
        self._attr_unique_id = f"{self._camera.serial}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._camera.serial)},
            name=camera,
            manufacturer=DEFAULT_BRAND,
            model=self._camera.camera_type,
        )

    def update(self) -> None:
        """Update sensor state."""
        state = self._camera.attributes[self.entity_description.key]
        _LOGGER.debug(
            "'%s' %s = %s",
            self._camera.attributes["name"],
            self.entity_description.key,
            state,
        )
        if self.entity_description.key == TYPE_BATTERY:
            state = state != "ok"
        self._attr_is_on = state
