"""Support for Velux covers."""
from pyvlx import OpeningDevice, Position
from pyvlx.opening_device import Awning, Blind, GarageDoor, Gate, RollerShutter, Window

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASS_AWNING,
    DEVICE_CLASS_BLIND,
    DEVICE_CLASS_GARAGE,
    DEVICE_CLASS_GATE,
    DEVICE_CLASS_SHUTTER,
    DEVICE_CLASS_WINDOW,
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    SUPPORT_STOP_TILT,
    CoverEntity,
)
from homeassistant.core import callback

from . import DATA_VELUX


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up cover(s) for Velux platform."""
    entities = []
    for node in hass.data[DATA_VELUX].pyvlx.nodes:
        if isinstance(node, OpeningDevice):
            entities.append(VeluxCover(node))
    async_add_entities(entities)


class VeluxCover(CoverEntity):
    """Representation of a Velux cover."""

    def __init__(self, node):
        """Initialize the cover."""
        self.node = node

    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""

        async def after_update_callback(device):
            """Call after device was updated."""
            self.async_write_ha_state()

        self.node.register_device_updated_cb(after_update_callback)

    async def async_added_to_hass(self):
        """Store register state change callback."""
        self.async_register_callbacks()

    @property
    def unique_id(self):
        """Return the unique ID of this cover."""
        return self.node.serial_number

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
        supported_features = (
            SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION | SUPPORT_STOP
        )
        if self.current_cover_tilt_position is not None:
            supported_features |= (
                SUPPORT_OPEN_TILT
                | SUPPORT_CLOSE_TILT
                | SUPPORT_SET_TILT_POSITION
                | SUPPORT_STOP_TILT
            )
        return supported_features

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return 100 - self.node.position.position_percent

    @property
    def current_cover_tilt_position(self):
        """Return the current position of the cover."""
        if isinstance(self.node, Blind):
            return 100 - self.node.orientation.position_percent
        return None

    @property
    def device_class(self):
        """Define this cover as either awning, blind, garage, gate, shutter or window."""
        if isinstance(self.node, Awning):
            return DEVICE_CLASS_AWNING
        if isinstance(self.node, Blind):
            return DEVICE_CLASS_BLIND
        if isinstance(self.node, GarageDoor):
            return DEVICE_CLASS_GARAGE
        if isinstance(self.node, Gate):
            return DEVICE_CLASS_GATE
        if isinstance(self.node, RollerShutter):
            return DEVICE_CLASS_SHUTTER
        if isinstance(self.node, Window):
            return DEVICE_CLASS_WINDOW
        return DEVICE_CLASS_WINDOW

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

            await self.node.set_position(
                Position(position_percent=position_percent), wait_for_completion=False
            )

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self.node.stop(wait_for_completion=False)

    async def async_close_cover_tilt(self, **kwargs):
        """Close cover tilt."""
        await self.node.close_orientation(wait_for_completion=False)

    async def async_open_cover_tilt(self, **kwargs):
        """Open cover tilt."""
        await self.node.open_orientation(wait_for_completion=False)

    async def async_stop_cover_tilt(self, **kwargs):
        """Stop cover tilt."""
        await self.node.stop_orientation(wait_for_completion=False)

    async def async_set_cover_tilt_position(self, **kwargs):
        """Move cover tilt to a specific position."""
        position_percent = 100 - kwargs[ATTR_TILT_POSITION]
        orientation = Position(position_percent=position_percent)
        await self.node.set_orientation(
            orientation=orientation, wait_for_completion=False
        )
