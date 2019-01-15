#from homeassistant.const import TEMP_CELSIUS
#from homeassistant.loader import get_component
#from homeassistant.const import CONF_TIMEOUT
from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA, BinarySensorDevice)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity

SENSORS = {
        'bypass_active': ["Danfoss Air Bypass Active", 'BYPASS_ACTIVE']
        }


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    """Set up the available Netatmo weather sensors."""
    data = hass.data["DANFOSS_DO"]

    dev = []

    for key in SENSORS.keys():
        dev.append(DanfossAirBinarySensor(data, SENSORS[key][0], SENSORS[key][1]))

    add_devices(dev, True)

class DanfossAirBinarySensor(BinarySensorDevice):
    """Representation of a Danfoss Air binary sensor."""

    def __init__(self, data, name, sensor_type):
        """Initialize the Danfoss Air binary sensor."""
        self._data = data
        self._name = name
        self._state = None
        self._type = sensor_type

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        return "opening"

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self._data.update()

        self._state = self._data.getValue(self._type)
