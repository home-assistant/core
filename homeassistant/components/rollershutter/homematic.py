"""
The homematic rollershutter platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/rollershutter.homematic/

Configuration:

rollershutter:
  - platform: homematic
    address: "<Homematic address for device>" # e.g. "JEQ0XXXXXXX"
    name: "<User defined name>"
"""

import logging
from homeassistant.const import (STATE_OPEN, STATE_CLOSED, STATE_UNKNOWN)
from homeassistant.components.rollershutter import RollershutterDevice,\
    ATTR_CURRENT_POSITION
import homeassistant.components.homematic as homematic


_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyhomematic==0.1.2']

# List of component names (string) your component depends upon.
DEPENDENCIES = ['homematic']


def setup_platform(hass, config, add_callback_devices, discovery_info=None):
    """Setup the platform."""
    return homematic.setup_hmdevice_entity_helper(HMRollershutter,
                                                  config,
                                                  add_callback_devices)


class HMRollershutter(homematic.HMDevice, RollershutterDevice):
    """Represents an Homematic Rollershutter in Home Assistant."""

    @property
    def current_position(self):
        """
        Return current position of roller shutter.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if self._is_connected:
            return int((1 - self._level) * 100)
        else:
            return None

    def position(self, **kwargs):
        """Move to a defined position: 0 (closed) and 100 (open)."""
        if self._is_connected:
            if ATTR_CURRENT_POSITION in kwargs:
                position = float(kwargs[ATTR_CURRENT_POSITION])
                position = min(100, max(0, position))
                self._hmdevice.level = (100 - position) / 100.0

    @property
    def state(self):
        """Return the state of the roller shutter."""
        current = self.current_position

        if current is None:
            return STATE_UNKNOWN

        return STATE_CLOSED if current == 100 else STATE_OPEN

    def move_up(self, **kwargs):
        """Move the roller shutter up."""
        if self._is_connected:
            self._hmdevice.move_up()

    def move_down(self, **kwargs):
        """Move the roller shutter down."""
        if self._is_connected:
            self._hmdevice.move_down()

    def stop(self, **kwargs):
        """Stop the device."""
        if self._is_connected:
            self._hmdevice.stop()

    def connect_to_homematic(self):
        """Configuration for device after connection with pyhomematic."""
        def event_received(device, caller, attribute, value):
            """Handler for received events."""
            attribute = str(attribute).upper()
            if attribute == 'LEVEL':
                # pylint: disable=attribute-defined-outside-init
                self._level = float(value)
            elif attribute == 'UNREACH':
                self._is_available = not bool(value)
            else:
                return
            self.update_ha_state()

        super().connect_to_homematic()
        if self._is_available:
            _LOGGER.debug("Setting up rollershutter %s",
                          # pylint: disable=protected-access
                          self._hmdevice._ADDRESS)
            self._hmdevice.setEventCallback(event_received)
            # pylint: disable=attribute-defined-outside-init
            self._level = self._hmdevice.level
            self.update_ha_state()
