"""Support for Velbus covers."""
import logging

from velbus.util import VelbusException

from homeassistant.components.cover import (
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
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
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._module.is_closed(self._channel)

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open
        """
        if self._module.is_closed(self._channel):
            return 0
        if self._module.is_open(self._channel):
            return 100
        return None

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
