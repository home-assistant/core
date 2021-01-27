"""Support for Lutron Caseta shades."""
import logging

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_SHADE,
    DOMAIN,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverEntity,
)

from . import LutronCasetaDevice
from .const import BRIDGE_DEVICE, BRIDGE_LEAP, DOMAIN as CASETA_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Lutron Caseta cover platform.

    Adds shades from the Caseta bridge associated with the config_entry as
    cover entities.
    """

    entities = []
    data = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    bridge = data[BRIDGE_LEAP]
    bridge_device = data[BRIDGE_DEVICE]
    cover_devices = bridge.get_devices_by_domain(DOMAIN)

    for cover_device in cover_devices:
        entity = LutronCasetaCover(cover_device, bridge, bridge_device)
        entities.append(entity)

    async_add_entities(entities, True)


class LutronCasetaCover(LutronCasetaDevice, CoverEntity):
    """Representation of a Lutron shade."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_SET_POSITION

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._device["current_state"] < 1

    @property
    def current_cover_position(self):
        """Return the current position of cover."""
        return self._device["current_state"]

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_SHADE

    async def async_stop_cover(self, **kwargs):
        """Top the cover."""
        await self._smartbridge.stop_cover(self.device_id)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self._smartbridge.lower_cover(self.device_id)
        self.async_update()
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._smartbridge.raise_cover(self.device_id)
        self.async_update()
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs):
        """Move the shade to a specific position."""
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            await self._smartbridge.set_value(self.device_id, position)

    async def async_update(self):
        """Call when forcing a refresh of the device."""
        self._device = self._smartbridge.get_device_by_id(self.device_id)
        _LOGGER.debug(self._device)
