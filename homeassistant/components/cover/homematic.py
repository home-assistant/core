"""
The HomeMatic cover platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.homematic/
"""
import logging
from homeassistant.const import STATE_UNKNOWN
from homeassistant.components.cover import CoverDevice, ATTR_POSITION, ATTR_TILT_POSITION
from homeassistant.components.homematic import HMDevice, ATTR_DISCOVER_DEVICES

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematic']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the platform."""
    if discovery_info is None:
        return

    devices = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        new_device = HMCover(conf)
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
            return self.current_cover_position == 0

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

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        try:
            return int(self._hmdevice.get_cover_tilt_position() * 100)
        except:
            return None

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        if ATTR_TILT_POSITION in kwargs:
            position = float(kwargs[ATTR_TILT_POSITION])
            position = min(100, max(0, position))
            level = position / 100.0
            self._hmdevice.set_cover_tilt_position(level, self._channel)

    def open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        self._hmdevice.open_slats()

    def close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        self._hmdevice.close_slats()

    def stop_cover_tilt(self, **kwargs):
        self.stop_cover(**kwargs)