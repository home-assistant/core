"""
Support for HomematicIP Cloud cover.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.homematicip_cloud/
"""
import logging

from homeassistant.components.cover import (
    ATTR_POSITION, ATTR_TILT_POSITION, CoverDevice)
from homeassistant.components.homematicip_cloud import (
    HMIPC_HAPID, HomematicipGenericDevice)
from homeassistant.components.homematicip_cloud import DOMAIN as HMIPC_DOMAIN

DEPENDENCIES = ['homematicip_cloud']

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the HomematicIP Cloud cover devices."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the HomematicIP cover from a config entry."""
    from homematicip.device import AsyncFullFlushShutter

    home = hass.data[HMIPC_DOMAIN][config_entry.data[HMIPC_HAPID]].home
    devices = []
    for device in home.devices:
        if isinstance(device, AsyncFullFlushShutter):
            devices.append(HomematicipCoverShutter(home, device))

    if devices:
        async_add_entities(devices)


class HomematicipCoverShutter(HomematicipGenericDevice, CoverDevice):
    """representation of a HomematicIP Cloud cover device."""

    def __init__(self, home, device):
        """Initialize the cover device."""
        super().__init__(home, device)

    @property
    def current_cover_position(self):
        """Return current position of cover."""
        return int(self._device.shutterLevel * 100)

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            position = float(kwargs[ATTR_POSITION])
            position = min(100, max(0, position))
            level = position / 100.0
            self._device.set_shutter_level(level)

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self._device.shutterLevel is not None:
            return self._device.shutterLevel == 0

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._device.set_shutter_level(1)

    def close_cover(self, **kwargs):
        """Close the cover."""
        self._device.set_shutter_level(0)

    def stop_cover(self, **kwargs):
        """Stop the device if in motion."""
        self._device.set_shutter_stop()
