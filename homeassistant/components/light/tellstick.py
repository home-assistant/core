"""
Support for Tellstick lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.tellstick/
"""
import voluptuous as vol

from homeassistant.components import tellstick
from homeassistant.components.light import (ATTR_BRIGHTNESS,
                                            SUPPORT_BRIGHTNESS, Light)
from homeassistant.components.tellstick import (DEFAULT_SIGNAL_REPETITIONS,
                                                ATTR_DISCOVER_DEVICES,
                                                ATTR_DISCOVER_CONFIG)

PLATFORM_SCHEMA = vol.Schema({vol.Required("platform"): tellstick.DOMAIN})

SUPPORT_TELLSTICK = SUPPORT_BRIGHTNESS


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Tellstick lights."""
    if (discovery_info is None or
            discovery_info[ATTR_DISCOVER_DEVICES] is None or
            tellstick.TELLCORE_REGISTRY is None):
        return

    signal_repetitions = discovery_info.get(ATTR_DISCOVER_CONFIG,
                                            DEFAULT_SIGNAL_REPETITIONS)

    add_devices(TellstickLight(
        tellstick.TELLCORE_REGISTRY.get_device(switch_id), signal_repetitions)
                for switch_id in discovery_info[ATTR_DISCOVER_DEVICES])


class TellstickLight(tellstick.TellstickDevice, Light):
    """Representation of a Tellstick light."""

    def __init__(self, tellstick_device, signal_repetitions):
        """Initialize the light."""
        self._brightness = 255
        tellstick.TellstickDevice.__init__(self,
                                           tellstick_device,
                                           signal_repetitions)

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_TELLSTICK

    def set_tellstick_state(self, last_command_sent, last_data_sent):
        """Update the internal representation of the switch."""
        from tellcore.constants import TELLSTICK_TURNON, TELLSTICK_DIM
        if last_command_sent == TELLSTICK_DIM:
            if last_data_sent is not None:
                self._brightness = int(last_data_sent)
            self._state = self._brightness > 0
        else:
            self._state = last_command_sent == TELLSTICK_TURNON

    def _send_tellstick_command(self, command, data):
        """Handle the turn_on / turn_off commands."""
        from tellcore.constants import (TELLSTICK_TURNOFF, TELLSTICK_DIM)
        if command == TELLSTICK_TURNOFF:
            self.tellstick_device.turn_off()
        elif command == TELLSTICK_DIM:
            self.tellstick_device.dim(self._brightness)
        else:
            raise NotImplementedError(
                "Command not implemented: {}".format(command))

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        from tellcore.constants import TELLSTICK_DIM
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            self._brightness = brightness

        self.call_tellstick(TELLSTICK_DIM, self._brightness)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        from tellcore.constants import TELLSTICK_TURNOFF
        self.call_tellstick(TELLSTICK_TURNOFF)
