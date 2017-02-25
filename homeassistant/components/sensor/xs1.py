import logging

from homeassistant.const import CONF_HOST, TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

from ..xs1 import XS1Device, DOMAIN, SENSORS


#DEPENDENCIES = ['xs1']
_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = ['temperature']

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    
    _LOGGER.info("initializing XS1 Sensor")
    
    sensors = hass.data[DOMAIN][SENSORS]
    
    _LOGGER.info("Adding Sensor devices...")
    
    for sensor in sensors:
        add_devices([XS1Sensor(sensor, hass)])


class XS1Sensor(XS1Device, Entity):
    """Representation of a Sensor."""

    def __init__(self, device, hass):
        """Initialize the sensor."""
        super().__init__(device, hass)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.device.name()

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.device.value()

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.device.unit()
        #return TEMP_CELSIUS

