"""Support for Blink system camera control."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_MOTION,
    BinarySensorEntity,
)

from .const import DOMAIN, TYPE_BATTERY, TYPE_CAMERA_ARMED, TYPE_MOTION_DETECTED

BINARY_SENSORS = {
    TYPE_BATTERY: ["Battery", DEVICE_CLASS_BATTERY],
    TYPE_CAMERA_ARMED: ["Camera Armed", None],
    TYPE_MOTION_DETECTED: ["Motion Detected", DEVICE_CLASS_MOTION],
}


async def async_setup_entry(hass, config, async_add_entities):
    """Set up the blink binary sensors."""
    data = hass.data[DOMAIN][config.entry_id]

    entities = []
    for camera in data.cameras:
        for sensor_type in BINARY_SENSORS:
            entities.append(BlinkBinarySensor(data, camera, sensor_type))
    async_add_entities(entities)


class BlinkBinarySensor(BinarySensorEntity):
    """Representation of a Blink binary sensor."""

    def __init__(self, data, camera, sensor_type):
        """Initialize the sensor."""
        self.data = data
        self._type = sensor_type
        name, device_class = BINARY_SENSORS[sensor_type]
        self._attr_name = f"{DOMAIN} {camera} {name}"
        self._attr_device_class = device_class
        self._camera = data.cameras[camera]
        self._attr_unique_id = f"{self._camera.serial}-{sensor_type}"

    def update(self):
        """Update sensor state."""
        self.data.refresh()
        state = self._camera.attributes[self._type]
        if self._type == TYPE_BATTERY:
            state = state != "ok"
        self._attr_is_on = state
