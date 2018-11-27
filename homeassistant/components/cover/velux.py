"""
Support for Velux covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.velux/
"""

from homeassistant.components.cover import (
    ATTR_POSITION, SUPPORT_CLOSE, SUPPORT_OPEN, SUPPORT_SET_POSITION,
    CoverDevice)
from homeassistant.components.velux import DATA_VELUX

DEPENDENCIES = ['velux']


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up cover(s) for Velux platform."""
    entities = []
    for node in hass.data[DATA_VELUX].pyvlx.nodes:
        from pyvlx.opening_device import OpeningDevice
        if isinstance(node, OpeningDevice):
            entities.append(VeluxCover(node))
    async_add_entities(entities)


class VeluxCover(CoverDevice):
    """Representation of a Velux cover."""

    def __init__(self, node):
        """Initialize the cover."""
        self.node = node

    @property
    def name(self):
        """Return the name of the Velux device."""
        return self.node.name

    @property
    def should_poll(self):
        """No polling needed within Velux."""
        return False

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | \
            SUPPORT_SET_POSITION

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return 0

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return None

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self.node.close()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self.node.close()

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            await self.node.set_position_percent(position)
