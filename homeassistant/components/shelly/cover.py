"""Cover for Shelly."""
from __future__ import annotations

from typing import Any, cast

from aioshelly import Block

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_SHUTTER,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ShellyDeviceWrapper
from .const import COAP, DATA_CONFIG_ENTRY, DOMAIN
from .entity import ShellyBlockEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up cover for device."""
    wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id][COAP]
    blocks = [block for block in wrapper.device.blocks if block.type == "roller"]

    if not blocks:
        return

    async_add_entities(ShellyCover(wrapper, block) for block in blocks)


class ShellyCover(ShellyBlockEntity, CoverEntity):
    """Switch that controls a cover block on Shelly devices."""

    _attr_device_class = DEVICE_CLASS_SHUTTER

    def __init__(self, wrapper: ShellyDeviceWrapper, block: Block) -> None:
        """Initialize light."""
        super().__init__(wrapper, block)
        self.control_result: dict[str, Any] | None = None
        self._supported_features: int = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP
        if self.wrapper.device.settings["rollers"][0]["positioning"]:
            self._supported_features |= SUPPORT_SET_POSITION

    @property
    def is_closed(self) -> bool:
        """If cover is closed."""
        if self.control_result:
            return cast(bool, self.control_result["current_pos"] == 0)

        return cast(bool, self.block.rollerPos == 0)

    @property
    def current_cover_position(self) -> int:
        """Position of the cover."""
        if self.control_result:
            return cast(int, self.control_result["current_pos"])

        return cast(int, self.block.rollerPos)

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        if self.control_result:
            return cast(bool, self.control_result["state"] == "close")

        return cast(bool, self.block.roller == "close")

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        if self.control_result:
            return cast(bool, self.control_result["state"] == "open")

        return cast(bool, self.block.roller == "open")

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        self.control_result = await self.set_state(go="close")
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        self.control_result = await self.set_state(go="open")
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        self.control_result = await self.set_state(
            go="to_pos", roller_pos=kwargs[ATTR_POSITION]
        )
        self.async_write_ha_state()

    async def async_stop_cover(self, **_kwargs: Any) -> None:
        """Stop the cover."""
        self.control_result = await self.set_state(go="stop")
        self.async_write_ha_state()

    @callback
    def _update_callback(self) -> None:
        """When device updates, clear control result that overrides state."""
        self.control_result = None
        super()._update_callback()
