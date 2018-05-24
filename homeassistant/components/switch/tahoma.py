"""
Support for Tahoma Switch - those are push buttons for garage door etc.

Those buttons are implemented as switches that are never on. They only
receive the turn_on action, perform the relay click, and stay in OFF state

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tahoma/
"""
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.components.tahoma import (
    DOMAIN as TAHOMA_DOMAIN, TahomaDevice)
from homeassistant.const import (STATE_OFF, STATE_ON)

DEPENDENCIES = ['tahoma']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Tahoma switches."""
    controller = hass.data[TAHOMA_DOMAIN]['controller']
    devices = []
    for switch in hass.data[TAHOMA_DOMAIN]['devices']['switch']:
        devices.append(TahomaSwitch(switch, controller))
    add_devices(devices, True)


class TahomaSwitch(TahomaDevice, SwitchDevice):
    """Representation a Tahoma Switch."""

    def __init__(self, tahoma_device, controller):
        """Initialize the switch."""
        self._state = STATE_OFF
        super().__init__(tahoma_device, controller)

    def update(self):
        """Update method."""
        self.controller.get_states([self.tahoma_device])
        if self.tahoma_device.type == 'io:OnOffLightIOComponent':
            if self.tahoma_device.active_states['core:OnOffState'] == 'on':
                self._state = STATE_ON
            else:
                self._state = STATE_OFF

    @property
    def device_class(self):
        """Return the class of the device."""
        if self.tahoma_device.type == 'rts:GarageDoor4TRTSComponent':
            return 'garage'
        return None

    def turn_on(self, **kwargs):
        """Send the on command."""
        _LOGGER.debug("Turn on: %s", self._name)
        if self.tahoma_device.type == 'rts:GarageDoor4TRTSComponent':
            self.toggle()
        else:
            self.apply_action('on')
            # FIXME: State immediately overwritten by update function.
            # How to deferre update, till REST request is done?
            self._state = STATE_ON

    def turn_off(self, **kwargs):
        """Send the off command."""
        _LOGGER.debug("Turn off: %s", self._name)
        if self.tahoma_device.type == 'rts:GarageDoor4TRTSComponent':
            return
        else:
            self.apply_action('off')
            # FIXME: State immediately overwritten by update function.
            # How to deferre update, till REST request is done?
            self._state = STATE_OFF

    def toggle(self, **kwargs):
        """Click the switch."""
        self.apply_action('cycle')

    @property
    def is_on(self):
        """Get whether the switch is in on state."""
        if self.tahoma_device.type == 'rts:GarageDoor4TRTSComponent':
            return False
        _LOGGER.debug("Is on (%s): %s", self._name, self._state)
        return bool(self._state == STATE_ON)
