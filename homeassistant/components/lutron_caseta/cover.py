"""Support for Lutron Caseta shades."""
import logging

from homeassistant.components.cover import (
    ATTR_POSITION, DOMAIN, SUPPORT_CLOSE, SUPPORT_OPEN, SUPPORT_SET_POSITION,
    CoverDevice)

from . import LUTRON_CASETA_SMARTBRIDGE, LutronCasetaDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Lutron Caseta shades as a cover device."""
    devs = []
    bridge = hass.data[LUTRON_CASETA_SMARTBRIDGE]
    cover_devices = bridge.get_devices_by_domain(DOMAIN)
    for cover_device in cover_devices:
        dev = LutronCasetaCover(cover_device, bridge)
        devs.append(dev)

    async_add_entities(devs, True)


class LutronCasetaCover(LutronCasetaDevice, CoverDevice):
    """Representation of a Lutron shade."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._state['current_state'] < 1

    @property
    def current_cover_position(self):
        """Return the current position of cover."""
        return self._state['current_state']

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        self._smartbridge.set_value(self._device_id, 0)

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        self._smartbridge.set_value(self._device_id, 100)

    async def async_set_cover_position(self, **kwargs):
        """Move the shade to a specific position."""
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            self._smartbridge.set_value(self._device_id, position)

    async def async_update(self):
        """Call when forcing a refresh of the device."""
        self._state = self._smartbridge.get_device_by_id(self._device_id)
        _LOGGER.debug(self._state)
