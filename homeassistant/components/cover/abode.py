"""
This component provides HA cover support for Abode Security System.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.abode/
"""
import logging

from homeassistant.components.abode import AbodeDevice, DOMAIN
from homeassistant.components.cover import CoverDevice


DEPENDENCIES = ['abode']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Abode cover devices."""
    import abodepy.helpers.constants as CONST

    data = hass.data[DOMAIN]

    devices = []
    for device in data.abode.get_devices(generic_type=CONST.TYPE_COVER):
        if device.device_id not in data.exclude:
            devices.append(AbodeCover(data, device))

    data.devices.extend(devices)

    add_devices(devices)


class AbodeCover(AbodeDevice, CoverDevice):
    """Representation of an Abode cover."""

    def __init__(self, data, device):
        """Initialize the Abode device."""
        AbodeDevice.__init__(self, data, device)

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        return self._device.is_open is False

    def close_cover(self, **kwargs):
        """Issue close command to cover."""
        self._device.close_cover()

    def open_cover(self, **kwargs):
        """Issue open command to cover."""
        self._device.open_cover()
