"""
Support for XS1 switches.

For more details about this platform, please refer to the documentation at
TODO: change Link
https://home-assistant.io/components/demo/
"""
import logging
import pprint
from ..xs1 import XS1Device, DOMAIN, ACTUATORS, SENSORS

from homeassistant.util.temperature import convert as convert_temperature

from homeassistant.components.climate import (
    STATE_AUTO, STATE_COOL, STATE_HEAT, ClimateDevice,
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE)
from homeassistant.const import (
    TEMP_CELSIUS, STATE_ON,
    STATE_OFF, STATE_UNKNOWN)

#DEPENDENCIES = ['xs1']
_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the XS1 platform."""
    _LOGGER.info("initializing XS1 Thermostat")
    
    from xs1_api_client import api_constants
    
    actuators = hass.data[DOMAIN][ACTUATORS]
    sensors = hass.data[DOMAIN][SENSORS]
    
    for actuator in actuators:
        if actuator.type() == api_constants.ACTUATOR_TYPE_THERMOSTAT:
            """Search for a matching sensor (by name)"""
            actuator_name = actuator.name()
            
            matching_sensor = None
            for sensor in sensors:
                if (actuator_name in sensor.name()):
                    matching_sensor = sensor
                    
                    break
            
            add_devices([XS1Thermostat(actuator, matching_sensor, hass)])
    
    _LOGGER.info("Added Thermostats!")
    

class XS1Thermostat(XS1Device, ClimateDevice):
    """Representation of a XS1 thermostat."""

    def __init__(self, device, sensor, hass):
        """Initialize the actuator."""
        super().__init__(device, hass)
        self.sensor = sensor

    @property
    def name(self):
        """Return the name of the device if any."""
        return self.device.name()
    
    @property
    def current_temperature(self):
        """Return the current temperature."""
        self.sensor.update()
        if not self.sensor == None:
            return self.sensor.value()
        else:
            return None
    
    @property
    def temperature_unit(self):
        """The unit of measurement used by the platform."""
        return self.device.unit()
        
    @property
    def target_temperature(self):
        """Returns the current target temperature."""
        self.update()
        return self.device.new_value()
        
    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert_temperature(8, TEMP_CELSIUS, self.unit_of_measurement)
        
    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert_temperature(25, TEMP_CELSIUS, self.unit_of_measurement)
        
    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        self.device.set_value(temp)
        if not self.sensor == None:
            self.sensor.update()
        
    def update(self):
        """We also have to update the sensor"""
        super().update()
        if not self.sensor == None:
            self.sensor.update()