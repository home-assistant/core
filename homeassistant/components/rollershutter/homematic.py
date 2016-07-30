"""
The homematic rollershutter platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/rollershutter.homematic/

Important: For this platform to work the homematic component has to be
properly configured.
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
    if discovery_info is None:
        return

    return homematic.setup_hmdevice_discovery_helper(HMRollershutter,
                                                     discovery_info,
                                                     add_callback_devices)


class HMRollershutter(homematic.HMDevice, RollershutterDevice):
    """Represents a Homematic Rollershutter in Home Assistant."""

    @property
    def current_position(self):
        """
        Return current position of rollershutter.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if self.available:
            return int((1 - self._hm_get_state()) * 100)
        return None

    def position(self, **kwargs):
        """Move to a defined position: 0 (closed) and 100 (open)."""
        if self.available:
            if ATTR_CURRENT_POSITION in kwargs:
                position = float(kwargs[ATTR_CURRENT_POSITION])
                position = min(100, max(0, position))
                level = (100 - position) / 100.0
                self._hmdevice.set_level(level, self._channel)

    @property
    def state(self):
        """Return the state of the rollershutter."""
        current = self.current_position
        if current is None:
            return STATE_UNKNOWN

        return STATE_CLOSED if current == 100 else STATE_OPEN

    def move_up(self, **kwargs):
        """Move the rollershutter up."""
        if self.available:
            self._hmdevice.move_up(self._channel)

    def move_down(self, **kwargs):
        """Move the rollershutter down."""
        if self.available:
            self._hmdevice.move_down(self._channel)

    def stop(self, **kwargs):
        """Stop the device if in motion."""
        if self.available:
            self._hmdevice.stop(self._channel)

    def _check_hm_to_ha_object(self):
        """Check if possible to use the HM Object as this HA type."""
        from pyhomematic.devicetypes.actors import Blind

        # Check compatibility from HMDevice
        if not super()._check_hm_to_ha_object():
            return False

        # Check if the homematic device is correct for this HA device
        if isinstance(self._hmdevice, Blind):
            return True

        _LOGGER.critical("This %s can't be use as rollershutter!", self._name)
        return False

    def _init_data_struct(self):
        """Generate a data dict (self._data) from hm metadata."""
        super()._init_data_struct()

        # Add state to data dict
        self._state = "LEVEL"
        self._data.update({self._state: STATE_UNKNOWN})
