"""
Support for long text sensors in app.
"""
import logging
from homeassistant.const import (CONF_NAME)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
DEFAULT_NAME = 'Long text Sensor'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    add_devices([LongTextSensor(
        config.get(CONF_NAME), config.get('package'), config.get('method'))])


class LongTextSensor(Entity):
    """Representation of a sensor that can have long text."""

    def __init__(self, name, package, method):
        """Initialize the sensor."""
        self._name = name
        self._package_to_import = package
        self._method_to_call_text = method

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        import importlib
        m = importlib.import_module(self._package_to_import)
        method_to_call = getattr(m, self._method_to_call_text)
        result = method_to_call()
        attr = {}
        attr['text'] = result
        return attr

    @property
    def state(self):
        return ''

    # def update(self):
    #     """Fetch new state data for the sensor.
    #     This is the only method that should fetch new data
    #     """
    #     self._state = 23
