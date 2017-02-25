"""
XS1 Sensor with 'boolean' value type
"""

from homeassistant.components.binary_sensor import BinarySensorDevice

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_devices, discovery_info=None):
    _LOGGER.info("initializing XS1 Binary Sensor")
    
    from xs1_api_client import api_constants
    
    for sensor in hass.data[DOMAIN][SENSORS]:
        if ((sensor.type() == api_constants.ACTUATOR_TYPE_SENSOR)
              and (actuator.unit() == api_constants.UNIT_BOOLEAN)):
            add_devices([XS1Switch(actuator, hass)])
    
    _LOGGER.info("Added Binary Sensors!")
    

class XS1BinarySensor(XS1Device, BinarySensorDevice):