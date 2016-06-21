"""
The homematic rollershutter platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/rollershutter.homematic/

Important: For this platform to work the homematic component has to be
properly configured.

Configuration:

rollershutter:
  - platform: homematic
    address: "<Homematic address for device>" # e.g. "JEQ0XXXXXXX"
    name: "<User defined name>" (optional)
"""

import logging
from homeassistant.const import (STATE_OPEN, STATE_CLOSED, STATE_UNKNOWN)
from homeassistant.components.rollershutter import RollershutterDevice,\
    ATTR_CURRENT_POSITION
import homeassistant.components.homematic as homematic


_LOGGER = logging.getLogger(__name__)

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
        if self.available:
            return int((1 - self._get_state()) * 100)
        return None

    def position(self, **kwargs):
        """Move to a defined position: 0 (closed) and 100 (open)."""
        if self.available:
            if ATTR_CURRENT_POSITION in kwargs:
                position = float(kwargs[ATTR_CURRENT_POSITION])
                position = min(100, max(0, position))
                level = (100 - position) / 100.0
                self._hmdevice.set_level(level, self._channel)
                self._set_state(level)

    @property
    def state(self):
        """Return the state of the roller shutter."""
        if not self.available:
            return STATE_UNKNOWN

        current = self.current_position
        if current is None:
            return STATE_UNKNOWN

        return STATE_CLOSED if current == 100 else STATE_OPEN

    def move_up(self, **kwargs):
        """Move the roller shutter up."""
        if self.available:
            self._hmdevice.move_up(self._channel)

    def move_down(self, **kwargs):
        """Move the roller shutter down."""
        if self.available:
            self._hmdevice.move_down(self._channel)

    def stop(self, **kwargs):
        """Stop the device."""
        if self.available:
            self._hmdevice.stop(self._channel)

    def _check_hm_to_ha_object(self):
        """
        Check if possible to use the HM Object as this HA type
        NEED overwrite by inheret!
        """
        from pyhomematic.devicetypes.actors import Blind

        # Check compatibility from HMDevice
        if not super()._check_hm_to_ha_object():
            return False

        # check if the homematic device correct for this HA device
        if isinstance(self._hmdevice, Blind):
            return True

        _LOGGER.critical("This %s can't be use as rollershutter!", self._name)
        return False

    def _init_data_struct(self):
        """
        Generate a data struct (self._data) from hm metadata
        NEED overwrite by inheret!
        """
        # add state to data struct
        self._state = "LEVEL"
        self._set_state(STATE_UNKNOWN)
