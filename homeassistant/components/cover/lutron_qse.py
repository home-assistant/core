"""
Support for Lutron QSE roller shade(e.g. Sivoia QS).

For more details about this platform, please refer to the documentation at
https: // home - assistant.io / components / cover.lutron_qse
"""
import logging

from homeassistant.components.cover import (
    CoverDevice, SUPPORT_OPEN, SUPPORT_CLOSE, SUPPORT_STOP,
    SUPPORT_SET_POSITION)
from homeassistant.components.lutron_qse import (
    LUTRON_QSE_INSTANCE, LUTRON_QSE_IGNORE, LutronQSEDevice)

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Lutron QSE roller shades as cover devices."""
    qse = hass.data[LUTRON_QSE_INSTANCE]
    ignore = hass.data[LUTRON_QSE_IGNORE]
    devices = []
    for roller in qse.rollers():
        if roller.serial_number in ignore:
            _LOGGER.info("Ignoring Lutron QSE Roller: %s",
                         roller.serial_number)
            continue
        devices.append(LutronQSECover(roller))
    add_devices(devices, True)


class LutronQSECover(LutronQSEDevice, CoverDevice):
    """Representation of a Lutron QSE roller shade."""

    def __init__(self, device):
        """Create a LutronQSECover instance."""
        LutronQSEDevice.__init__(self, device)
        self._is_closing = False
        self._is_opening = False
        self._position = 0
        self._update()

    def _update(self):
        """Update state from device."""
        self._is_opening = self._device.opening
        self._is_closing = self._device.closing
        self._position = self._device.target_level

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'window'

    @property
    def supported_features(self):
        """Flag supported features."""
        return (SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION |
                SUPPORT_STOP)

    @property
    def current_cover_position(self):
        """Return the current position of cover."""
        return self._position

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._is_opening

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._is_closing

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._position == 0

    def open_cover(self):
        """Open the cover."""
        self._device.open()

    def close_cover(self):
        """Close the cover."""
        self._device.close()

    def set_cover_position(self, position, **kwargs):
        """Move the roller shutter to a specific position."""
        self._device.set_target_level(position)

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._device.stop()
