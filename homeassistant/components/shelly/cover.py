"""Cover for Shelly."""
from aioshelly import Block

from homeassistant.components.cover import (
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverEntity,
)
from homeassistant.const import (
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import callback

from . import ShellyBlockEntity, ShellyDeviceWrapper
from .const import DOMAIN


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
        self._supported_features = 0
        self._supported_features |= SUPPORT_OPEN
        self._supported_features |= SUPPORT_CLOSE
        self._supported_features |= SUPPORT_STOP
        if self.wrapper.device.settings["rollers"][0]["positioning"]:
            self._supported_features |= SUPPORT_SET_POSITION

    @property
    def is_closed(self):
        """If cover is closed."""
        if self.control_result:
            return self.control_result["rollerPos"] == 0

        return self.block.rollerPos == 0

    @property
    def current_cover_position(self):
        """Position of the cover."""
        if self.control_result:
            return self.control_result["rollerPos"]
        else:
            return self.block.rollerPos

    @property
    def is_closing(self):
        """Return if the cover is closing."""
        return self.block.roller == "close"

    @property
    def is_opening(self):
        """Return if the cover is opening."""
        return self.block.roller == "open"

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    def close_cover(self, **_kwargs):
        """Close the cover."""
        self.device.down()

    def open_cover(self, **_kwargs):
        """Open the cover."""
        self.device.up()

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        pos = kwargs[ATTR_POSITION]
        self.device.rollerPos(pos)
        self._position = pos

    def stop_cover(self, **_kwargs):
        """Stop the cover."""
        self.device.stop()

    @callback
    def _update_callback(self):
        """When device updates, clear control result that overrides state."""
        self.control_result = None
        super()._update_callback()
