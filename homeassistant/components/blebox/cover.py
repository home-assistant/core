"""BleBox cover entity."""

from homeassistant.components.cover import (
    ATTR_POSITION,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPENING,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverEntity,
)

from . import BleBoxEntity, create_blebox_entities
from .const import BLEBOX_TO_HASS_COVER_STATES, BLEBOX_TO_HASS_DEVICE_CLASSES


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a BleBox entry."""

    create_blebox_entities(
        hass, config_entry, async_add_entities, BleBoxCoverEntity, "covers"
    )


class BleBoxCoverEntity(BleBoxEntity, CoverEntity):
    """Representation of a BleBox cover feature."""

    def __init__(self, feature):
        """Initialize a BleBox cover feature."""
        super().__init__(feature)
        self._attr_device_class = BLEBOX_TO_HASS_DEVICE_CLASSES[feature.device_class]
        position = SUPPORT_SET_POSITION if feature.is_slider else 0
        stop = SUPPORT_STOP if feature.has_stop else 0
        self._attr_supported_features = position | stop | SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def state(self):
        """Return the equivalent HA cover state."""
        return BLEBOX_TO_HASS_COVER_STATES[self._feature.state]

    @property
    def current_cover_position(self):
        """Return the current cover position."""
        position = self._feature.current
        if position == -1:  # possible for shutterBox
            return None

        return None if position is None else 100 - position

    @property
    def is_opening(self):
        """Return whether cover is opening."""
        return self._is_state(STATE_OPENING)

    @property
    def is_closing(self):
        """Return whether cover is closing."""
        return self._is_state(STATE_CLOSING)

    @property
    def is_closed(self):
        """Return whether cover is closed."""
        return self._is_state(STATE_CLOSED)

    async def async_open_cover(self, **kwargs):
        """Open the cover position."""
        await self._feature.async_open()

    async def async_close_cover(self, **kwargs):
        """Close the cover position."""
        await self._feature.async_close()

    async def async_set_cover_position(self, **kwargs):
        """Set the cover position."""

        position = kwargs[ATTR_POSITION]
        await self._feature.async_set_position(100 - position)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self._feature.async_stop()

    def _is_state(self, state_name):
        value = self.state
        return None if value is None else value == state_name
