"""Support for Wink covers."""
from homeassistant.components.cover import ATTR_POSITION, CoverDevice

from . import DOMAIN, WinkDevice


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Wink cover platform."""
    import pywink

    for shade in pywink.get_shades():
        _id = shade.object_id() + shade.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_entities([WinkCoverDevice(shade, hass)])
    for shade in pywink.get_shade_groups():
        _id = shade.object_id() + shade.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_entities([WinkCoverDevice(shade, hass)])
    for door in pywink.get_garage_doors():
        _id = door.object_id() + door.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_entities([WinkCoverDevice(door, hass)])


class WinkCoverDevice(WinkDevice, CoverDevice):
    """Representation of a Wink cover device."""

    async def async_added_to_hass(self):
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
        return None

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        state = self.wink.state()
        return bool(state == 0)
