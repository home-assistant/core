"""
Support for switching devices via pilight to on and off.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.pilight/
"""
import logging

from homeassistant.helpers.config_validation import ensure_list
import homeassistant.components.pilight as pilight
from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = ['pilight']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the pilight platform."""
    # Find and return switches controlled by pilight
    switches = config.get('switches', {})
    devices = []

    for dev_name, properties in switches.items():
        devices.append(
            PilightSwitch(
                hass,
                properties.get('name', dev_name),
                properties.get('on_code'),
                properties.get('off_code'),
                ensure_list(properties.get('on_code_receive', False)),
                ensure_list(properties.get('off_code_receive', False))))

    add_devices_callback(devices)


class PilightSwitch(SwitchDevice):
    """Representation of a pilight switch."""

    # pylint: disable=too-many-arguments, too-many-instance-attributes
    def __init__(self, hass, name, code_on, code_off,
                 code_on_receive, code_off_receive):
        """Initialize the switch."""
        self._hass = hass
        self._name = name
        self._state = False
        self._code_on = code_on
        self._code_off = code_off
        self._code_on_receive = code_on_receive
        self._code_off_receive = code_off_receive

        if any(self._code_on_receive) or any(self._code_off_receive):
            hass.bus.listen(pilight.EVENT, self._handle_code)

    @property
    def name(self):
        """Get the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed, state set when correct code is received."""
        return False

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def _handle_code(self, call):
        """Check if received code by the pilight-daemon.

        If the code matches the receive on / off codes of this switch
        the switch state is changed accordingly.
        """
        # Check if a on code is defined to turn this switch on
        if any(self._code_on_receive):
            for on_code in self._code_on_receive:  # Loop through codes
                # True if on_code is contained in received code dict, not
                # all items have to match
                if on_code.items() <= call.data.items():
                    self.turn_on()
                    # Call turn on only once, even when more than one on
                    # code is received
                    break

        # Check if a off code is defined to turn this switch off
        if any(self._code_off_receive):
            for off_code in self._code_off_receive:  # Loop through codes
                # True if off_code is contained in received code dict, not
                # all items have to match
                if off_code.items() <= call.data.items():
                    self.turn_off()
                    # Call turn off only once, even when more than one off
                    # code is received
                    break

    def turn_on(self):
        """Turn the switch on by calling pilight.send service with on code."""
        self._hass.services.call(pilight.DOMAIN, pilight.SERVICE_NAME,
                                 self._code_on, blocking=True)
        self._state = True
        self.update_ha_state()

    def turn_off(self):
        """Turn the switch on by calling pilight.send service with off code."""
        self._hass.services.call(pilight.DOMAIN, pilight.SERVICE_NAME,
                                 self._code_off, blocking=True)
        self._state = False
        self.update_ha_state()
