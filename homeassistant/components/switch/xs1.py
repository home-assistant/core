"""
Support for XS1 switches.

For more details about this platform, please refer to the documentation at
TODO: change Link
https://home-assistant.io/components/demo/
"""
import logging
from ..xs1 import XS1Device, DOMAIN, ACTUATORS

from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import DEVICE_DEFAULT_NAME

#DEPENDENCIES = ['xs1']
_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the XS1 platform."""
    _LOGGER.info("initializing XS1 Switch")
    
    from xs1_api_client import api_constants
    
    actuators = hass.data[DOMAIN][ACTUATORS]
    
    for actuator in actuators:
        if ((actuator.type() == api_constants.ACTUATOR_TYPE_SWITCH) 
              or (actuator.type() == api_constants.ACTUATOR_TYPE_DIMMER)):
            add_devices([XS1Switch(actuator, hass)])
    
    _LOGGER.info("Added Switches!")


class XS1Switch(XS1Device, ToggleEntity):
    """Representation of a XS1 switch actuator."""

    def __init__(self, device, hass):
        """Initialize the actuator."""
        super().__init__(device, hass)

    @property
    def name(self):
        """Return the name of the device if any."""
        return self.device.name()

    @property
    def is_on(self):
        """Return true if switch is on."""
        self.update()
        return self.device.value() == 100

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.device.turn_on()
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.device.turn_off()
        self.schedule_update_ha_state()