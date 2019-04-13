"""Support for Abode Security System covers."""
import logging

from homeassistant.components.cover import CoverDevice

from . import DOMAIN as ABODE_DOMAIN, AbodeDevice

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Abode cover devices."""
    import abodepy.helpers.constants as CONST

    data = hass.data[ABODE_DOMAIN]

    devices = []
    for device in data.abode.get_devices(generic_type=CONST.TYPE_COVER):
        if data.is_excluded(device):
            continue

        devices.append(AbodeCover(data, device))

    data.devices.extend(devices)

    add_entities(devices)


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
