"""
The homematic cover platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.homematic/

Important: For this platform to work the homematic component has to be
properly configured.
"""

import logging
from homeassistant.const import STATE_UNKNOWN
from homeassistant.components.cover import CoverDevice,\
    ATTR_POSITION
import homeassistant.components.homematic as homematic

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematic']


def setup_platform(hass, config, add_callback_devices, discovery_info=None):
    """Setup the platform."""
    if discovery_info is None:
        return

    return homematic.setup_hmdevice_discovery_helper(
        HMCover,
        discovery_info,
        add_callback_devices
    )


# pylint: disable=abstract-method
class HMCover(homematic.HMDevice, CoverDevice):
    """Represents a Homematic Cover in Home Assistant."""

    @property
    def current_cover_position(self):
        """
        Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if self.available:
            return int(self._hm_get_state() * 100)
        return None

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        if self.available:
            if ATTR_POSITION in kwargs:
                position = float(kwargs[ATTR_POSITION])
                position = min(100, max(0, position))
                level = position / 100.0
                self._hmdevice.set_level(level, self._channel)

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self.current_cover_position is not None:
            if self.current_cover_position > 0:
                return False
            else:
                return True

    def open_cover(self, **kwargs):
        """Open the cover."""
        if self.available:
            self._hmdevice.move_up(self._channel)

    def close_cover(self, **kwargs):
        """Close the cover."""
        if self.available:
            self._hmdevice.move_down(self._channel)

    def stop_cover(self, **kwargs):
        """Stop the device if in motion."""
        if self.available:
            self._hmdevice.stop(self._channel)

    def _init_data_struct(self):
        """Generate a data dict (self._data) from hm metadata."""
        # Add state to data dict
        self._state = "LEVEL"
        self._data.update({self._state: STATE_UNKNOWN})
