"""
Support for switching devices via pilight to on and off.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.pilight/
"""
import logging

import homeassistant.components.pilight as pilight
from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = ['pilight']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the pilight platform."""
    # Verify that pilight-daemon connection is present
    if not pilight.CONNECTED:
        _LOGGER.error('A connection has not been made to the pilight-daemon')
        return False

    """Find and return switches controlled by pilight"""
    switches = config.get('switches', {})
    devices = []

    for dev_name, properties in switches.items():
        devices.append(
            PilightSwitch(
                hass,
                properties.get('name', dev_name),
                properties.get('on_code'),
                properties.get('off_code'),
                properties.get('on_code_receive', False),
                properties.get('off_code_receive', False)))

    add_devices_callback(devices)


class PilightSwitch(SwitchDevice):
    """Representation of a pilight switch."""

    # pylint: disable=too-many-arguments, too-many-instance-attributes
    def __init__(self, hass, name, code_on, code_off, code_on_receive, code_off_receive):
        """Initialize the switch."""
        self._hass = hass
        self._name = name
        self._state = False
        self._code_on = code_on
        self._code_off = code_off
        self._code_on_receive = code_on_receive
        self._code_off_receive = code_off_receive
        
        if self._code_on_receive or self._code_off_receive:
            hass.bus.listen(pilight.EVENT, self._set_state)

    @property
    def name(self):
        """Get the name of the switch"""
        return self._name
    
    @property
    def should_poll(self):
        """No polling needed, state can be set when correct code is received"""
        return False

    @property
    def is_on(self):
        """Return true if switch is on"""
        return self._state
    
    def _set_state(self, call):
        ''' Check if received code by the pilight-daemon matches the receive on/off codes of this switch.
        If it does change the switch state accordingly.
        '''

        if self._code_on_receive:  # Check if a on code is defined to turn this switch on
            if isinstance(self._code_on_receive, list):  # Several on codes are defined
                for on_code in self._code_on_receive:
                    if on_code.items() <= call.data.items():  # True if on_code is contained in received code dict, not all items have to match
                        self.turn_on()
                        break  # Call turn on only once, even when more than one on code is received
            elif self._code_on_receive.items() <= call.data.items():
                self.turn_on()
            
        if self._code_off_receive:  # Check if a off code is defined to turn this switch off
            if isinstance(self._code_off_receive, list):  # Several off codes are defined
                for off_code in self._code_off_receive:
                    if off_code.items() <= call.data.items():  # True if off_code is contained in received code dict, not all items have to match
                        self.turn_off()
                        break  # Call turn off only once, even when more than one off code is received
            elif self._code_off_receive.items() <= call.data.items():
                self.turn_off()

    def turn_on(self):
        """Turn the switch on by calling the pilight send service with the on code"""
        self._hass.services.call(pilight.DOMAIN, pilight.SERVICE_NAME, self._code_on, blocking=True)
        self._state = True
        self.update_ha_state()

    def turn_off(self):
        """Turn the switch on by calling the pilight send service with the off code"""
        self._hass.services.call(pilight.DOMAIN, pilight.SERVICE_NAME, self._code_off, blocking=True)
        self._state = False
        self.update_ha_state()
