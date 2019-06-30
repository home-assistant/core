"""Support for Velbus covers."""
import logging

from homeassistant.components.cover import (
    CoverDevice, SUPPORT_CLOSE, SUPPORT_OPEN, SUPPORT_STOP)

from . import DOMAIN as VELBUS_DOMAIN, VelbusEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Velbus xover platform."""
    if discovery_info is None:
        return
    covers = []
    for cover in discovery_info:
        module = hass.data[VELBUS_DOMAIN].get_module(cover[0])
        channel = cover[1]
        covers.append(VelbusCover(module, channel))
    async_add_entities(covers)


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
        self._module.open(self._channel)

    def close_cover(self, **kwargs):
        """Close the cover."""
        self._module.close(self._channel)

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._module.stop(self._channel)
