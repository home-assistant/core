"""Support for  HomeMatic covers."""
import logging

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverEntity,
)

from .const import ATTR_DISCOVER_DEVICES
from .entity import HMDevice

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the platform."""
    if discovery_info is None:
        return

    devices = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        new_device = HMCover(conf)
        devices.append(new_device)

    add_entities(devices, True)


class HMCover(HMDevice, CoverEntity):
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
        return None

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
        """Generate a data dictionary (self._data) from metadata."""
        self._state = "LEVEL"
        self._data.update({self._state: None})
        if "LEVEL_2" in self._hmdevice.WRITENODE:
            self._data.update({"LEVEL_2": None})

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if "LEVEL_2" not in self._data:
            return None

        return int(self._data.get("LEVEL_2", 0) * 100)

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        if "LEVEL_2" in self._data and ATTR_TILT_POSITION in kwargs:
            position = float(kwargs[ATTR_TILT_POSITION])
            position = min(100, max(0, position))
            level = position / 100.0
            self._hmdevice.set_cover_tilt_position(level, self._channel)

    def open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        if "LEVEL_2" in self._data:
            self._hmdevice.open_slats()

    def close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        if "LEVEL_2" in self._data:
            self._hmdevice.close_slats()

    def stop_cover_tilt(self, **kwargs):
        """Stop cover tilt."""
        if "LEVEL_2" in self._data:
            self.stop_cover(**kwargs)
