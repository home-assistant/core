"""
Support for Eufy switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.eufy/
"""
import logging

from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = ['eufy']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Eufy switches."""
    if discovery_info is None:
        return
    add_devices([EufySwitch(discovery_info)], True)


class EufySwitch(SwitchDevice):
    """Representation of a Eufy switch."""

    def __init__(self, device):
        """Initialize the light."""
        import lakeside

        self._state = None
        self._name = device['name']
        self._address = device['address']
        self._code = device['code']
        self._type = device['type']
        self._switch = lakeside.switch(self._address, self._code, self._type)
        self._switch.connect()

    def update(self):
        """Synchronise state from the switch."""
        self._switch.update()
        self._state = self._switch.power

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._address

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the specified switch on."""
        try:
            self._switch.set_state(True)
        except BrokenPipeError:
            self._switch.connect()
            self._switch.set_state(power=True)

    def turn_off(self, **kwargs):
        """Turn the specified switch off."""
        try:
            self._switch.set_state(False)
        except BrokenPipeError:
            self._switch.connect()
            self._switch.set_state(False)
