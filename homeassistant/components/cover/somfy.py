"""
Support for Somfy Covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.somfy/
"""
from pymfy.api.devices.blind import Blind
from pymfy.api.devices.category import Category
from pymfy.api.devices.roller_shutter import RollerShutter

from homeassistant.components.cover import CoverDevice, ATTR_POSITION, \
    ATTR_TILT_POSITION
from homeassistant.components.somfy import DOMAIN, SomfyEntity, DEVICES

DEPENDENCIES = ['somfy']

CATEGORIES = {Category.ROLLER_SHUTTER.value, Category.INTERIOR_BLIND.value,
              Category.EXTERIOR_BLIND.value}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Somfy cover platform."""
    devices = hass.data[DOMAIN][DEVICES]
    for cover in devices:
        if CATEGORIES & set(cover.categories):
            add_entities([SomfyCover(cover, hass)])


class SomfyCover(SomfyEntity, CoverDevice):
    """Representation of a Somfy cover device."""

    def close_cover(self, **kwargs):
        """Close the cover."""
        RollerShutter(self.device, self.api).close()

    def open_cover(self, **kwargs):
        """Open the cover."""
        RollerShutter(self.device, self.api).open()

    def stop_cover(self, **kwargs):
        """Stop the cover"""
        RollerShutter(self.device, self.api).stop()

    def set_cover_position(self, **kwargs):
        """Move the cover shutter to a specific position."""
        position = kwargs.get(ATTR_POSITION)
        RollerShutter(self.device, self.api).set_position(100 - position)

    @property
    def current_cover_position(self):
        """Return the current position of cover shutter."""
        position = None
        try:
            shutter = RollerShutter(self.device, self.api)
            position = 100 - shutter.get_position()
        except StopIteration:
            pass
        return position

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        is_closed = None
        try:
            is_closed = RollerShutter(self.device, self.api).is_closed()
        except StopIteration:
            pass
        return is_closed

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        orientation = None
        try:
            orientation = Blind(self.device, self.api).orientation
        except StopIteration:
            pass
        return orientation

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        orientation = kwargs.get(ATTR_TILT_POSITION)
        Blind(self.device, self.api).orientation = orientation

    def open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        Blind(self.device, self.api).orientation = 100

    def close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        Blind(self.device, self.api).orientation = 0

    def stop_cover_tilt(self, **kwargs):
        """Stop the cover."""
        Blind(self.device, self.api).stop()
