"""Support for Abode Security System covers."""
import abodepy.helpers.constants as CONST

from homeassistant.components.cover import CoverDevice

from . import AbodeDevice
from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Abode cover devices."""
    data = hass.data[DOMAIN]

    entities = []

    for device in data.abode.get_devices(generic_type=CONST.TYPE_COVER):
        entities.append(AbodeCover(data, device))

    async_add_entities(entities)


class AbodeCover(AbodeDevice, CoverDevice):
    """Representation of an Abode cover."""

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        return not self._device.is_open

    def close_cover(self, **kwargs):
        """Issue close command to cover."""
        self._device.close_cover()

    def open_cover(self, **kwargs):
        """Issue open command to cover."""
        self._device.open_cover()
