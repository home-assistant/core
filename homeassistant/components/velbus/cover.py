"""Support for Velbus covers."""
import logging

from velbus.util import VelbusException

from homeassistant.components.cover import (
    ATTR_POSITION,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverDevice,
)

from . import VelbusEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Velbus cover based on config_entry."""
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    modules_data = hass.data[DOMAIN][entry.entry_id]["cover"]
    entities = []
    for address, channel in modules_data:
        module = cntrl.get_module(address)
        entities.append(VelbusCover(module, channel))
    async_add_entities(entities)


class VelbusCover(VelbusEntity, CoverDevice):
    """Representation a Velbus cover."""

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._module.support_position():
            return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_SET_POSITION
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self._module.get_position(self._channel) == 100:
            return True
        return False

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open
        Velbus: 100 = closed, 0 = open
        """
        pos = self._module.get_position(self._channel)
        return 100 - pos

    def open_cover(self, **kwargs):
        """Open the cover."""
        try:
            self._module.open(self._channel)
        except VelbusException as err:
            _LOGGER.error("A Velbus error occurred: %s", err)

    def close_cover(self, **kwargs):
        """Close the cover."""
        try:
            self._module.close(self._channel)
        except VelbusException as err:
            _LOGGER.error("A Velbus error occurred: %s", err)

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        try:
            self._module.stop(self._channel)
        except VelbusException as err:
            _LOGGER.error("A Velbus error occurred: %s", err)

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        try:
            self._module.set(self._channel, (100 - kwargs[ATTR_POSITION]))
        except VelbusException as err:
            _LOGGER.error("A Velbus error occurred: %s", err)
