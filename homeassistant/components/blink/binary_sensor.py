"""Support for Blink system camera control."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_MOTION,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .const import DOMAIN, TYPE_BATTERY, TYPE_CAMERA_ARMED, TYPE_MOTION_DETECTED

BINARY_SENSORS_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key=TYPE_BATTERY,
        name="Battery",
        device_class=DEVICE_CLASS_BATTERY,
    ),
    BinarySensorEntityDescription(
        key=TYPE_CAMERA_ARMED,
        name="Camera Armed",
    ),
    BinarySensorEntityDescription(
        key=TYPE_MOTION_DETECTED,
        name="Motion Detected",
        device_class=DEVICE_CLASS_MOTION,
    ),
)


async def async_setup_entry(hass, config, async_add_entities):
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

    def __init__(self, data, camera, description: BinarySensorEntityDescription):
        """Initialize the sensor."""
        self.data = data
        self.entity_description = description
        self._attr_name = f"{DOMAIN} {camera} {description.name}"
        self._camera = data.cameras[camera]
        self._attr_unique_id = f"{self._camera.serial}-{description.key}"

    def update(self):
        """Update sensor state."""
        self.data.refresh()
        state = self._camera.attributes[self.entity_description.key]
        if self.entity_description.key == TYPE_BATTERY:
            state = state != "ok"
        self._attr_is_on = state
