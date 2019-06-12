"""Support for Lupusec Security System switches."""
from datetime import timedelta
import logging

from homeassistant.components.switch import SwitchDevice

from . import DOMAIN as LUPUSEC_DOMAIN, LupusecDevice

SCAN_INTERVAL = timedelta(seconds=2)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Lupusec switch devices."""
    if discovery_info is None:
        return

    import lupupy.constants as CONST

    data = hass.data[LUPUSEC_DOMAIN]

    devices = []

    for device in data.lupusec.get_devices(generic_type=CONST.TYPE_SWITCH):

        devices.append(LupusecSwitch(data, device))

    add_entities(devices)


class LupusecSwitch(LupusecDevice, SwitchDevice):
    """Representation of a Lupusec switch."""

    def turn_on(self, **kwargs):
        """Turn on the device."""
        self._device.switch_on()

    def turn_off(self, **kwargs):
        """Turn off the device."""
        self._device.switch_off()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device.is_on
