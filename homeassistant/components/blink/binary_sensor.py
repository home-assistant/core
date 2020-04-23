"""Support for Blink system camera control."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_MONITORED_CONDITIONS

from . import BINARY_SENSORS, BLINK_DATA


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the blink binary sensors."""
    if discovery_info is None:
        return
    data = hass.data[BLINK_DATA]

    devs = []
    for camera in data.cameras:
        for sensor_type in discovery_info[CONF_MONITORED_CONDITIONS]:
            devs.append(BlinkBinarySensor(data, camera, sensor_type))
    add_entities(devs, True)


class BlinkBinarySensor(BinarySensorEntity):
    """Representation of a Blink binary sensor."""

    def __init__(self, data, camera, sensor_type):
        """Initialize the sensor."""
        self.data = data
        self._type = sensor_type
        name, icon = BINARY_SENSORS[sensor_type]
        self._name = f"{BLINK_DATA} {camera} {name}"
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
