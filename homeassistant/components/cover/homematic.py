"""
The HomeMatic cover platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.homematic/
"""
import logging
from homeassistant.const import STATE_UNKNOWN
from homeassistant.components.cover import CoverDevice, ATTR_POSITION
from homeassistant.components.homematic import HMDevice, ATTR_DISCOVER_DEVICES

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematic']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the platform."""
    if discovery_info is None:
        return

    devices = []
    for config in discovery_info[ATTR_DISCOVER_DEVICES]:
        new_device = HMCover(hass, config)
        new_device.link_homematic()
        devices.append(new_device)

    add_devices(devices)


class HMCover(HMDevice, CoverDevice):
    """Representation a HomeMatic Cover."""

    @property
    def current_cover_position(self):
        """
        Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return int(self._hm_get_state() * 100)

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
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
        self._hmdevice.move_up(self._channel)

    def close_cover(self, **kwargs):
        """Close the cover."""
        self._hmdevice.move_down(self._channel)

    def stop_cover(self, **kwargs):
        """Stop the device if in motion."""
        self._hmdevice.stop(self._channel)

    def _init_data_struct(self):
        """Generate a data dictoinary (self._data) from metadata."""
        self._state = "LEVEL"
        self._data.update({self._state: STATE_UNKNOWN})
