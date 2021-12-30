"""Cover component for shades controlled by the Wevolor controller."""

from __future__ import annotations

from pywevolor import Wevolor

from homeassistant.components.cover import (
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_STOP,
    SUPPORT_STOP_TILT,
    CoverDeviceClass,
    CoverEntity,
)

from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Wevolor shades."""

    entities = []
    wevolor = hass.data[DOMAIN][config_entry.entry_id]

    channel_ids = range(1, config_entry.data["channel_count"] + 1)

    for channel_id in channel_ids:
        entity = WevolorShade(wevolor, channel_id, config_entry.data["support_tilt"])
        entities.append(entity)

    async_add_entities(entities, True)


class WevolorShade(CoverEntity):
    """Cover entity for control of Wevolor remote channel."""

    _channel: int | None = None
    _wevolor: Wevolor | None = None
    _attr_assumed_state = True
    _support_tilt: bool = False

    def __init__(self, wevolor: Wevolor, channel: int, support_tilt: bool = False):
        """Create this wevolor shade cover entity."""
        self._wevolor = wevolor
        self._channel = channel
        self._support_tilt = support_tilt

    @property
    def device_class(self):
        """Return the device class."""
        return CoverDeviceClass.BLIND if self._support_tilt else CoverDeviceClass.SHADE

    @property
    def name(self):
        """Return the name of the device."""
        return f"Wevolor Channel #{self._channel}"

    @property
    def supported_features(self):
        """Flag supported features."""
        flags = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP
        if self._support_tilt:
            return flags | SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT | SUPPORT_STOP_TILT

        return flags

    async def async_stop_cover(self, **kwargs):
        """Stop motion."""
        await self._wevolor.stop_blind(self._channel)

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._wevolor.open_blind(self._channel)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self._wevolor.close_blind(self._channel)

    async def async_open_cover_tilt(self, **kwargs):
        """Open tilt."""
        await self._wevolor.open_blind_tilt(self._channel)

    async def async_close_cover_tilt(self, **kwargs):
        """Close tilt."""
        await self._wevolor.close_blind_tilt(self._channel)

    async def async_stop_cover_tilt(self, **kwargs):
        """Stop tilt."""
        await self._wevolor.stop_blind_tilt(self._channel)

    @property
    def is_closed(self) -> bool | None:
        """Since Wevolor does not expose any status, return None here."""
        return None
