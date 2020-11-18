"""Light for Shelly."""
from typing import Optional

from aioshelly import Block

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP,
    LightEntity,
)
from homeassistant.core import callback
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

from . import ShellyDeviceWrapper
from .const import DATA_CONFIG_ENTRY, DOMAIN
from .entity import ShellyBlockEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up lights for device."""
    wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id]
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
        if hasattr(block, "colorTemp"):
            self._supported_features |= SUPPORT_COLOR_TEMP

    @property
    def supported_features(self) -> int:
        """Supported features."""
        return self._supported_features

    @property
    def is_on(self) -> bool:
        """If light is on."""
        if self.control_result:
            return self.control_result["ison"]

        return self.block.output

    @property
    def brightness(self) -> Optional[int]:
        """Brightness of light."""
        if self.control_result:
            brightness = self.control_result["brightness"]
        else:
            brightness = self.block.brightness
        return int(brightness / 100 * 255)

    @property
    def color_temp(self) -> Optional[float]:
        """Return the CT color value in mireds."""
        if self.control_result:
            color_temp = self.control_result["temp"]
        else:
            color_temp = self.block.colorTemp

        # If you set DUO to max mireds in Shelly app, 2700K,
        # It reports 0 temp
        if color_temp == 0:
            return self.max_mireds

        return int(color_temperature_kelvin_to_mired(color_temp))

    @property
    def min_mireds(self) -> float:
        """Return the coldest color_temp that this light supports."""
        return color_temperature_kelvin_to_mired(6500)

    @property
    def max_mireds(self) -> float:
        """Return the warmest color_temp that this light supports."""
        return color_temperature_kelvin_to_mired(2700)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on light."""
        params = {"turn": "on"}
        if ATTR_BRIGHTNESS in kwargs:
            tmp_brightness = kwargs[ATTR_BRIGHTNESS]
            params["brightness"] = int(tmp_brightness / 255 * 100)
        if ATTR_COLOR_TEMP in kwargs:
            color_temp = color_temperature_mired_to_kelvin(kwargs[ATTR_COLOR_TEMP])
            if color_temp > 6500:
                color_temp = 6500
            elif color_temp < 2700:
                color_temp = 2700
            params["temp"] = int(color_temp)
        self.control_result = await self.block.set_state(**params)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off light."""
        self.control_result = await self.block.set_state(turn="off")
        self.async_write_ha_state()

    @callback
    def _update_callback(self):
        """When device updates, clear control result that overrides state."""
        self.control_result = None
        super()._update_callback()
