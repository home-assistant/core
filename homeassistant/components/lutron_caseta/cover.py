"""Support for Lutron Caseta shades."""
import logging

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverEntity,
)

from . import DOMAIN as CASETA_DOMAIN, LutronCasetaDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Lutron Caseta cover platform.

    Adds shades from the Caseta bridge associated with the config_entry as
    cover entities.
    """

    entities = []
    bridge = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    cover_devices = bridge.get_devices_by_domain(DOMAIN)

    for cover_device in cover_devices:
        entity = LutronCasetaCover(cover_device, bridge)
        entities.append(entity)

    async_add_entities(entities, True)


class LutronCasetaCover(LutronCasetaDevice, CoverEntity):
    """Representation of a Lutron shade."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._device["current_state"] < 1

    @property
    def current_cover_position(self):
        """Return the current position of cover."""
        return self._device["current_state"]

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        self._smartbridge.set_value(self.device_id, 0)

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        self._smartbridge.set_value(self.device_id, 100)

    async def async_set_cover_position(self, **kwargs):
        """Move the shade to a specific position."""
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            self._smartbridge.set_value(self.device_id, position)

    async def async_update(self):
        """Call when forcing a refresh of the device."""
        self._device = self._smartbridge.get_device_by_id(self.device_id)
        _LOGGER.debug(self._device)
