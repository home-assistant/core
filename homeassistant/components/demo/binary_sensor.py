"""Demo platform that has two fake binary sensors."""
from homeassistant.components.binary_sensor import BinarySensorDevice


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Demo binary sensor platform."""
    add_entities([
        DemoBinarySensor('Basement Floor Wet', False, 'moisture'),
        DemoBinarySensor('Movement Backyard', True, 'motion'),
    ])


class DemoBinarySensor(BinarySensorDevice):
    """representation of a Demo binary sensor."""

    def __init__(self, name, state, device_class):
        """Initialize the demo sensor."""
        self._name = name
        self._state = state
        self._sensor_type = device_class

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._sensor_type

    @property
    def should_poll(self):
        """No polling needed for a demo binary sensor."""
        return False

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state
