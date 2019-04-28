"""Support for Lutron shades."""
import logging

from homeassistant.components.cover import (
    ATTR_POSITION, SUPPORT_CLOSE, SUPPORT_OPEN, SUPPORT_SET_POSITION,
    CoverDevice)

from . import LUTRON_CONTROLLER, LUTRON_DEVICES, LutronDevice

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Lutron shades."""
    devs = []
    for (area_name, device) in hass.data[LUTRON_DEVICES]['cover']:
        dev = LutronCover(area_name, device, hass.data[LUTRON_CONTROLLER])
        devs.append(dev)

    add_entities(devs, True)
    return True


class LutronCover(LutronDevice, CoverDevice):
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
        _LOGGER.debug("Lutron ID: %d updated to %f",
                      self._lutron_device.id, level)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        attr['Lutron Integration ID'] = self._lutron_device.id
        return attr
