import logging

"""
The homematic switch platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.homematic/
"""

from homeassistant.components.switch import SwitchDevice
import homeassistant.components.homematic as homematic

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyhomematic==0.1.2']

# List of component names (string) your component depends upon.
DEPENDENCIES = ['homematic']


def setup_platform(hass, config, add_callback_devices, discovery_info=None):
    return homematic.setup_hmdevice_entity_helper(HMSwitch, config, add_callback_devices)


class HMSwitch(homematic.HMDevice, SwitchDevice):
    """Represents an Homematic Switch in Home Assistant."""
            
    @property
    def is_on(self):
        """Return True if switch is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the switch."""
        return not self.available

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        if self._is_connected:
            self._hmdevice.on()
            self._state = True

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        if self._is_connected:
            self._hmdevice.off()
            self._state = False

    def connect_to_homematic(self):
        """Configuration specific to device after connection with pyhomematic is established"""
        def event_received(device, caller, attribute, value):
            attribute = str(attribute).upper()
            if attribute == 'LEVEL':
                self._level = float(value)
            elif attribute == 'STATE':
                self._state = bool(value)
            elif attribute == 'UNREACH':
                self._is_available = not bool(value)
            else:
                return
            self.update_ha_state()

        super().connect_to_homematic()

        if hasattr(self._hmdevice, 'level'):
            self._dimmer = True 
        else:
            self._dimmer = False 
        if self._is_available:
            _LOGGER.debug("Setting up switch-device %s" % self._hmdevice._ADDRESS)
            self._hmdevice.setEventCallback(event_received)
            if self._dimmer:
                self._level = self._hmdevice.level
            else:
                self._state = self._hmdevice.is_on
            self.update_ha_state()
