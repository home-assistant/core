"""Support for Lutron shades."""
import logging

from homeassistant.components.cover import (
    ATTR_POSITION,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverEntity,
)

from . import LUTRON_CONTROLLER, LUTRON_DEVICES, LutronDevice
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up covers for a single Lutron deployment."""
    async_add_entities(
        (
            LutronCover(
                area, device, hass.data[DOMAIN][entry.entry_id][LUTRON_CONTROLLER],
            )
            for (area, device) in hass.data[DOMAIN][entry.entry_id][LUTRON_DEVICES][
                "cover"
            ]
        ),
        True,
    )


class LutronCover(LutronDevice, CoverEntity):
    """Representation of a Lutron shade."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._lutron_device.last_level() < 1

    @property
    def current_cover_position(self):
        """Return the current position of cover."""
        return self._lutron_device.last_level()

    def close_cover(self, **kwargs):
        """Close the cover."""
        self._lutron_device.level = 0

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._lutron_device.level = 100

    def set_cover_position(self, **kwargs):
        """Move the shade to a specific position."""
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            self._lutron_device.level = position

    def update(self):
        """Call when forcing a refresh of the device."""
        # Reading the property (rather than last_level()) fetches value
        level = self._lutron_device.level
        _LOGGER.debug("Lutron ID: %d updated to %f", self._lutron_device.id, level)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        attr["Lutron Integration ID"] = self._lutron_device.id
        return attr
