"""
Support for Wink Covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.wink/
"""
import asyncio

from homeassistant.components.cover import CoverDevice, STATE_UNKNOWN, \
    ATTR_POSITION
from homeassistant.components.wink import WinkDevice, DOMAIN

DEPENDENCIES = ['wink']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Wink cover platform."""
    import pywink

    for shade in pywink.get_shades():
        _id = shade.object_id() + shade.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkCoverDevice(shade, hass)])
    for door in pywink.get_garage_doors():
        _id = door.object_id() + door.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkCoverDevice(door, hass)])


class WinkCoverDevice(WinkDevice, CoverDevice):
    """Representation of a Wink cover device."""

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.data[DOMAIN]['entities']['cover'].append(self)

    def close_cover(self, **kwargs):
        """Close the cover."""
        self.wink.set_state(0)

    def open_cover(self, **kwargs):
        """Open the cover."""
        self.wink.set_state(1)

    def set_cover_position(self, **kwargs):
        """Move the cover shutter to a specific position."""
        position = kwargs.get(ATTR_POSITION)
        self.wink.set_state(position/100)

    @property
    def current_cover_position(self):
        """Return the current position of cover shutter."""
        if self.wink.state() is not None:
            return int(self.wink.state()*100)
        return STATE_UNKNOWN

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        state = self.wink.state()
        return bool(state == 0)
