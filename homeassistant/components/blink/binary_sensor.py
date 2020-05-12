"""Support for Blink system camera control."""
from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import DOMAIN, TYPE_CAMERA_ARMED, TYPE_MOTION_DETECTED

BINARY_SENSORS = {
    TYPE_CAMERA_ARMED: ["Camera Armed", "mdi:verified"],
    TYPE_MOTION_DETECTED: ["Motion Detected", "mdi:run-fast"],
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
        name, icon = BINARY_SENSORS[sensor_type]
        self._name = f"{DOMAIN} {camera} {name}"
        self._icon = icon
        self._camera = data.cameras[camera]
        self._state = None
        self._unique_id = f"{self._camera.serial}-{self._type}"

    @property
    def name(self):
        """Return the name of the blink sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state

    def update(self):
        """Update sensor state."""
        self.data.refresh()
        self._state = self._camera.attributes[self._type]
