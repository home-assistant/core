"""
Support for Vera lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.vera/
"""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
from homeassistant.const import (STATE_OFF, STATE_ON)
from homeassistant.components.vera import (
    VeraDevice, VERA_DEVICES, VERA_CONTROLLER)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['vera']

SUPPORT_VERA = SUPPORT_BRIGHTNESS


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Vera lights."""
    add_devices(
        VeraLight(device, VERA_CONTROLLER) for device in VERA_DEVICES['light'])


class VeraLight(VeraDevice, Light):
    """Representation of a Vera Light, including dimmable."""

    def __init__(self, vera_device, controller):
        """Initialize the light."""
        self._state = False
        VeraDevice.__init__(self, vera_device, controller)

    @property
    def brightness(self):
        """Return the brightness of the light."""
        if self.vera_device.is_dimmable:
            return self.vera_device.get_brightness()

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_VERA

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs and self.vera_device.is_dimmable:
            self.vera_device.set_brightness(kwargs[ATTR_BRIGHTNESS])
        else:
            self.vera_device.switch_on()

        self._state = STATE_ON
        self.update_ha_state(True)

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self.vera_device.switch_off()
        self._state = STATE_OFF
        self.update_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def update(self):
        """Called by the vera device callback to update state."""
        self._state = self.vera_device.is_switched_on()
