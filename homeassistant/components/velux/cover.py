"""Support for Velux covers."""
from homeassistant.components.cover import (
    ATTR_POSITION, SUPPORT_CLOSE, SUPPORT_OPEN, SUPPORT_SET_POSITION,
    SUPPORT_STOP, CoverDevice)
from homeassistant.core import callback

from . import DATA_VELUX


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up cover(s) for Velux platform."""
    entities = []
    for node in hass.data[DATA_VELUX].pyvlx.nodes:
        from pyvlx import OpeningDevice
        if isinstance(node, OpeningDevice):
            entities.append(VeluxCover(node))
    async_add_entities(entities)


class VeluxCover(CoverDevice):
    """Representation of a Velux cover."""

    def __init__(self, node):
        """Initialize the cover."""
        self.node = node

    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""
        async def after_update_callback(device):
            """Call after device was updated."""
            await self.async_update_ha_state()
        self.node.register_device_updated_cb(after_update_callback)

    async def async_added_to_hass(self):
        """Store register state change callback."""
        self.async_register_callbacks()

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
            SUPPORT_SET_POSITION | SUPPORT_STOP

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return 100 - self.node.position.position_percent

    @property
    def device_class(self):
        """Define this cover as a window."""
        return 'window'

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self.node.position.closed

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self.node.close(wait_for_completion=False)

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self.node.open(wait_for_completion=False)

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            position_percent = 100 - kwargs[ATTR_POSITION]
            from pyvlx import Position
            await self.node.set_position(
                Position(position_percent=position_percent),
                wait_for_completion=False)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self.node.stop(wait_for_completion=False)
