"""
Support for Lutron Caseta SerenaRollerShade.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.lutron_caseta/
"""
import logging


from homeassistant.components.cover import (
    CoverDevice, SUPPORT_OPEN, SUPPORT_CLOSE)
from homeassistant.components.lutron_caseta import (
    LUTRON_CASETA_SMARTBRIDGE, LutronCasetaDevice)


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['lutron_caseta']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Lutron Caseta Serena shades as a cover device."""
    devs = []
    bridge = hass.data[LUTRON_CASETA_SMARTBRIDGE]
    cover_devices = bridge.get_devices_by_types(["SerenaRollerShade"])
    for cover_device in cover_devices:
        dev = LutronCasetaCover(cover_device, bridge)
        devs.append(dev)

    add_devices(devs, True)


class LutronCasetaCover(LutronCasetaDevice, CoverDevice):
    """Representation of a Lutron Serena shade."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._state["current_state"] < 1

    def close_cover(self):
        """Close the cover."""
        self._smartbridge.set_value(self._device_id, 0)

    def open_cover(self):
        """Open the cover."""
        self._smartbridge.set_value(self._device_id, 100)

    def set_cover_position(self, position, **kwargs):
        """Move the roller shutter to a specific position."""
        self._smartbridge.set_value(self._device_id, position)

    def update(self):
        """Call when forcing a refresh of the device."""
        self._state = self._smartbridge.get_device_by_id(self._device_id)
        _LOGGER.debug(self._state)
