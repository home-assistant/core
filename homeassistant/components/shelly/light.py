"""Light for Shelly."""
from aioshelly import Block

from homeassistant.components.light import SUPPORT_BRIGHTNESS, LightEntity
from homeassistant.core import callback

from . import ShellyDeviceWrapper
from .const import DOMAIN
from .entity import ShellyBlockEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up lights for device."""
    wrapper = hass.data[DOMAIN][config_entry.entry_id]
    blocks = [block for block in wrapper.device.blocks if block.type == "light"]

    if not blocks:
        return

    async_add_entities(ShellyLight(wrapper, block) for block in blocks)


class ShellyLight(ShellyBlockEntity, LightEntity):
    """Switch that controls a relay block on Shelly devices."""

    def __init__(self, wrapper: ShellyDeviceWrapper, block: Block) -> None:
        """Initialize light."""
        super().__init__(wrapper, block)
        self.control_result = None
        self._supported_features = 0
        if hasattr(block, "brightness"):
            self._supported_features |= SUPPORT_BRIGHTNESS

    @property
    def is_on(self) -> bool:
        """If light is on."""
        if self.control_result:
            return self.control_result["ison"]

        return self.block.output

    @property
    def brightness(self):
        """Brightness of light."""
        if self.control_result:
            brightness = self.control_result["brightness"]
        else:
            brightness = self.block.brightness
        return int(brightness / 100 * 255)

    @property
    def supported_features(self):
        """Supported features."""
        return self._supported_features

    async def async_turn_on(
        self, brightness=None, **kwargs
    ):  # pylint: disable=arguments-differ
        """Turn on light."""
        params = {"turn": "on"}
        if brightness is not None:
            params["brightness"] = int(brightness / 255 * 100)
        self.control_result = await self.block.set_state(**params)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off light."""
        self.control_result = await self.block.set_state(turn="off")
        self.async_write_ha_state()

    @callback
    def _update_callback(self):
        """When device updates, clear control result that overrides state."""
        self.control_result = None
        super()._update_callback()
