"""Cover for Shelly."""
from aioshelly import Block

from homeassistant.components.cover import (
    ATTR_POSITION,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverEntity,
)
from homeassistant.core import callback

from . import ShellyDeviceWrapper
from .const import DOMAIN
from .entity import ShellyBlockEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up cover for device."""
    wrapper = hass.data[DOMAIN][config_entry.entry_id]
    blocks = [block for block in wrapper.device.blocks if block.type == "roller"]

    if not blocks:
        return

    async_add_entities(ShellyCover(wrapper, block) for block in blocks)


class ShellyCover(ShellyBlockEntity, CoverEntity):
    """Switch that controls a cover block on Shelly devices."""

    def __init__(self, wrapper: ShellyDeviceWrapper, block: Block) -> None:
        """Initialize light."""
        super().__init__(wrapper, block)
        self.control_result = None
        self._supported_features = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP
        if self.wrapper.device.settings["rollers"][0]["positioning"]:
            self._supported_features |= SUPPORT_SET_POSITION

    @property
    def is_closed(self):
        """If cover is closed."""
        if self.control_result:
            return self.control_result["current_pos"] == 0

        return self.block.rollerPos == 0

    @property
    def current_cover_position(self):
        """Position of the cover."""
        if self.control_result:
            return self.control_result["current_pos"]

        return self.block.rollerPos

    @property
    def is_closing(self):
        """Return if the cover is closing."""
        if self.control_result:
            return self.control_result["state"] == "close"

        return self.block.roller == "close"

    @property
    def is_opening(self):
        """Return if the cover is opening."""
        if self.control_result:
            return self.control_result["state"] == "open"

        return self.block.roller == "open"

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        self.control_result = await self.block.set_state(go="close")
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open cover."""
        self.control_result = await self.block.set_state(go="open")
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        self.control_result = await self.block.set_state(
            go="to_pos", roller_pos=kwargs[ATTR_POSITION]
        )
        self.async_write_ha_state()

    async def async_stop_cover(self, **_kwargs):
        """Stop the cover."""
        self.control_result = await self.block.set_state(go="stop")
        self.async_write_ha_state()

    @callback
    def _update_callback(self):
        """When device updates, clear control result that overrides state."""
        self.control_result = None
        super()._update_callback()
