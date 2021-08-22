"""Support for Velbus covers."""
import logging

from homeassistant.components.cover import (
    ATTR_POSITION,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverEntity,
)

from . import VelbusEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Velbus switch based on config_entry."""
    await hass.data[DOMAIN][entry.entry_id]["tsk"]
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    entities = []
    for channel in cntrl.get_all("cover"):
        entities.append(VelbusCover(channel))
    async_add_entities(entities)


class VelbusCover(VelbusEntity, CoverEntity):
    """Representation a Velbus cover."""

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._channel.support_position():
            return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_SET_POSITION
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._channel.is_closed()

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open
        Velbus: 100 = closed, 0 = open
        """
        pos = self._channel.get_position()
        return 100 - pos

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._channel.open()

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self._channel.close()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self._channel.stop()

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        self._channel.set_position(100 - kwargs[ATTR_POSITION])
