"""Support for the Dynalite channels as covers."""

from typing import Any

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    CoverDeviceClass,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.enum import try_parse_enum

from .bridge import DynaliteBridge
from .dynalitebase import DynaliteBase, async_setup_entry_base


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Record the async_add_entities function to add them later when received from Dynalite."""

    @callback
    def cover_from_device(device: Any, bridge: DynaliteBridge) -> CoverEntity:
        if device.has_tilt:
            return DynaliteCoverWithTilt(device, bridge)
        return DynaliteCover(device, bridge)

    async_setup_entry_base(
        hass, config_entry, async_add_entities, "cover", cover_from_device
    )


class DynaliteCover(DynaliteBase, CoverEntity):
    """Representation of a Dynalite Channel as a Home Assistant Cover."""

    def __init__(self, device: Any, bridge: DynaliteBridge) -> None:
        """Initialize the cover."""
        super().__init__(device, bridge)
        device_class = try_parse_enum(CoverDeviceClass, self._device.device_class)
        self._attr_device_class = device_class or CoverDeviceClass.SHUTTER

    @property
    def current_cover_position(self) -> int:
        """Return the position of the cover from 0 to 100."""
        return self._device.current_cover_position

    @property
    def is_opening(self) -> bool:
        """Return true if cover is opening."""
        return self._device.is_opening

    @property
    def is_closing(self) -> bool:
        """Return true if cover is closing."""
        return self._device.is_closing

    @property
    def is_closed(self) -> bool:
        """Return true if cover is closed."""
        return self._device.is_closed

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._device.async_open_cover(**kwargs)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._device.async_close_cover(**kwargs)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position."""
        await self._device.async_set_cover_position(**kwargs)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._device.async_stop_cover(**kwargs)

    def initialize_state(self, state):
        """Initialize the state from cache."""
        target_level = state.attributes.get(ATTR_CURRENT_POSITION)
        if target_level is not None:
            self._device.init_level(target_level)


class DynaliteCoverWithTilt(DynaliteCover):
    """Representation of a Dynalite Channel as a Home Assistant Cover that uses up and down for tilt."""

    @property
    def current_cover_tilt_position(self) -> int:
        """Return the current tilt position."""
        return self._device.current_cover_tilt_position

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open cover tilt."""
        await self._device.async_open_cover_tilt(**kwargs)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close cover tilt."""
        await self._device.async_close_cover_tilt(**kwargs)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Set the cover tilt position."""
        await self._device.async_set_cover_tilt_position(**kwargs)

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilt."""
        await self._device.async_stop_cover_tilt(**kwargs)
