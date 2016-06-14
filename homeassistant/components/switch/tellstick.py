"""
Support for Tellstick switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tellstick/
"""
import voluptuous as vol

from homeassistant.components import tellstick
from homeassistant.components.tellstick import (ATTR_DISCOVER_DEVICES,
                                                ATTR_DISCOVER_CONFIG)
from homeassistant.helpers.entity import ToggleEntity

PLATFORM_SCHEMA = vol.Schema({vol.Required("platform"): tellstick.DOMAIN})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Tellstick switches."""
    if (discovery_info is None or
            discovery_info[ATTR_DISCOVER_DEVICES] is None or
            tellstick.TELLCORE_REGISTRY is None):
        return

    # Allow platform level override, fallback to module config
    signal_repetitions = discovery_info.get(
        ATTR_DISCOVER_CONFIG, tellstick.DEFAULT_SIGNAL_REPETITIONS)

    add_devices(TellstickSwitchDevice(
        tellstick.TELLCORE_REGISTRY.get_device(switch_id), signal_repetitions)
                for switch_id in discovery_info[ATTR_DISCOVER_DEVICES])


class TellstickSwitchDevice(tellstick.TellstickDevice, ToggleEntity):
    """Representation of a Tellstick switch."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def set_tellstick_state(self, last_command_sent, last_data_sent):
        """Update the internal representation of the switch."""
        from tellcore.constants import TELLSTICK_TURNON
        self._state = last_command_sent == TELLSTICK_TURNON

    def _send_tellstick_command(self, command, data):
        """Handle the turn_on / turn_off commands."""
        from tellcore.constants import TELLSTICK_TURNON, TELLSTICK_TURNOFF
        if command == TELLSTICK_TURNON:
            self.tellstick_device.turn_on()
        elif command == TELLSTICK_TURNOFF:
            self.tellstick_device.turn_off()

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        from tellcore.constants import TELLSTICK_TURNON
        self.call_tellstick(TELLSTICK_TURNON)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        from tellcore.constants import TELLSTICK_TURNOFF
        self.call_tellstick(TELLSTICK_TURNOFF)
