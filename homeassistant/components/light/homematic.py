<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
=======
import logging

>>>>>>> Added Homematic implementation
"""
The homematic custom light platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.homematic/
"""

<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
import logging
=======
>>>>>>> Added Homematic implementation
from homeassistant.components.light import (ATTR_BRIGHTNESS, Light)
import homeassistant.components.homematic as homematic

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyhomematic==0.1.2']

# List of component names (string) your component depends upon.
DEPENDENCIES = ['homematic']


def setup_platform(hass, config, add_callback_devices, discovery_info=None):
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
    """Setup the platform."""
=======
>>>>>>> Added Homematic implementation
    return homematic.setup_hmdevice_entity_helper(HMLight, config, add_callback_devices)


class HMLight(homematic.HMDevice, Light):
    """Represents an Homematic Light in Home Assistant."""
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
=======
            
    @property
    def brightness(self):
        """Return the brightness of this light between 0..255"""
>>>>>>> Added Homematic implementation
        if self._dimmer:
            return int(self._level * 255)
        else:
            return None
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf

=======
    
>>>>>>> Added Homematic implementation
    @property
    def is_on(self):
        """Return True if light is on."""
        if self._is_connected:
            if self._dimmer:
                return self._level > 0
            else:
                return self._state
        else:
            return False
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf

=======
        
>>>>>>> Added Homematic implementation
    def turn_on(self, **kwargs):
        """Turn the light on."""
        if self._is_connected:
            if ATTR_BRIGHTNESS in kwargs and self._dimmer:
                percent_bright = float(kwargs[ATTR_BRIGHTNESS]) / 255
                self._hmdevice.level = percent_bright
            else:
                self._state = True
                self._hmdevice.on()

    def turn_off(self, **kwargs):
        """Turn the light off."""
        if self._is_connected:
            if not self._dimmer:
                self._state = False
            self._hmdevice.off()
<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf

    def connect_to_homematic(self):
        """Configuration specific to device after connection with pyhomematic is established."""
        def event_received(device, caller, attribute, value):
            """Handler for received events."""
            attribute = str(attribute).upper()
            if attribute == 'LEVEL':
                # pylint: disable=attribute-defined-outside-init
=======
            
    def connect_to_homematic(self):
        """Configuration specific to device after connection with pyhomematic is established"""
        def event_received(device, caller, attribute, value):
            attribute = str(attribute).upper()
            if attribute == 'LEVEL':
>>>>>>> Added Homematic implementation
                self._level = float(value)
            elif attribute == 'STATE':
                self._state = bool(value)
            elif attribute == 'UNREACH':
                self._is_available = not bool(value)
            else:
                return
            self.update_ha_state()

        super().connect_to_homematic()

<<<<<<< a28681b5c6dc2eefcd492192d5b82772b4a3d8cf
        # pylint: disable=attribute-defined-outside-init
        self._dimmer = bool(hasattr(self._hmdevice, 'level'))

        if self._is_available:
            # pylint: disable=protected-access
            _LOGGER.debug("Setting up light device %s", self._hmdevice._ADDRESS)
            self._hmdevice.setEventCallback(event_received)
            if self._dimmer:
                # pylint: disable=attribute-defined-outside-init
=======
        if hasattr(self._hmdevice, 'level'):
            self._dimmer = True 
        else:
            self._dimmer = False 
        if self._is_available:
            _LOGGER.debug("Setting up light device %s" % self._hmdevice._ADDRESS)
            self._hmdevice.setEventCallback(event_received)
            if self._dimmer:
>>>>>>> Added Homematic implementation
                self._level = self._hmdevice.level
            else:
                self._state = self._hmdevice.is_on
            self.update_ha_state()
