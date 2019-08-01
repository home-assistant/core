"""Support for HomematicIP Cloud cover devices."""
import logging
from typing import Optional

from homematicip.aio.device import AsyncFullFlushBlind, AsyncFullFlushShutter

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDevice,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import DOMAIN as HMIPC_DOMAIN, HMIPC_HAPID, HomematicipGenericDevice

_LOGGER = logging.getLogger(__name__)

HMIP_COVER_OPEN = 0
HMIP_COVER_CLOSED = 1
HMIP_SLATS_OPEN = 0
HMIP_SLATS_CLOSED = 1


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the HomematicIP Cloud cover devices."""
    pass


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the HomematicIP cover from a config entry."""
    home = hass.data[HMIPC_DOMAIN][config_entry.data[HMIPC_HAPID]].home
    devices = []
    for device in home.devices:
        if isinstance(device, AsyncFullFlushBlind):
            devices.append(HomematicipCoverSlats(home, device))
        elif isinstance(device, AsyncFullFlushShutter):
            devices.append(HomematicipCoverShutter(home, device))

    if devices:
        async_add_entities(devices)


class HomematicipCoverShutter(HomematicipGenericDevice, CoverDevice):
    """Representation of a HomematicIP Cloud cover shutter device."""

    @property
    def current_cover_position(self) -> int:
        """Return current position of cover."""
        return int((1 - self._device.shutterLevel) * 100)

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        # HmIP cover is closed:1 -> open:0
        level = 1 - position / 100.0
        await self._device.set_shutter_level(level)

    @property
    def is_closed(self) -> Optional[bool]:
        """Return if the cover is closed."""
        if self._device.shutterLevel is not None:
            return self._device.shutterLevel == HMIP_COVER_CLOSED
        return None

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._device.set_shutter_level(HMIP_COVER_OPEN)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self._device.set_shutter_level(HMIP_COVER_CLOSED)

    async def async_stop_cover(self, **kwargs):
        """Stop the device if in motion."""
        await self._device.set_shutter_stop()


class HomematicipCoverSlats(HomematicipCoverShutter, CoverDevice):
    """Representation of a HomematicIP Cloud cover slats device."""

    @property
    def current_cover_tilt_position(self) -> int:
        """Return current tilt position of cover."""
        return int((1 - self._device.slatsLevel) * 100)

    async def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover to a specific tilt position."""
        position = kwargs[ATTR_TILT_POSITION]
        # HmIP slats is closed:1 -> open:0
        level = 1 - position / 100.0
        await self._device.set_slats_level(level)

    async def async_open_cover_tilt(self, **kwargs):
        """Open the slats."""
        await self._device.set_slats_level(HMIP_SLATS_OPEN)

    async def async_close_cover_tilt(self, **kwargs):
        """Close the slats."""
        await self._device.set_slats_level(HMIP_SLATS_CLOSED)

    async def async_stop_cover_tilt(self, **kwargs):
        """Stop the device if in motion."""
        await self._device.set_shutter_stop()
