"""Light for Shelly."""
from typing import Optional

from aioshelly import Block

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.core import callback
from homeassistant.util.color import (
    color_hs_to_RGB,
    color_RGB_to_hs,
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

from . import ShellyDeviceWrapper
from .const import COAP, DATA_CONFIG_ENTRY, DOMAIN
from .entity import ShellyBlockEntity
from .utils import async_remove_shelly_entity

SUPPORT_SHELLYRGB_COLOR = SUPPORT_BRIGHTNESS | SUPPORT_COLOR
SUPPORT_SHELLYRGB_WHITE = SUPPORT_BRIGHTNESS


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up lights for device."""
    wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id][COAP]

    blocks = []
    for block in wrapper.device.blocks:
        if block.type == "light":
            blocks.append(block)
        elif block.type == "relay":
            appliance_type = wrapper.device.settings["relays"][int(block.channel)].get(
                "appliance_type"
            )
            if appliance_type and appliance_type.lower() == "light":
                blocks.append(block)
                unique_id = (
                    f'{wrapper.device.shelly["mac"]}-{block.type}_{block.channel}'
                )
                await async_remove_shelly_entity(hass, "switch", unique_id)

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
        if hasattr(block, "white"):
            self._supported_features |= SUPPORT_WHITE_VALUE
        if hasattr(block, "red") and hasattr(block, "green") and hasattr(block, "blue"):
            if wrapper.device.settings["mode"] == "color":
                self._supported_features |= SUPPORT_SHELLYRGB_COLOR
            elif wrapper.device.settings["mode"] == "white":
                self._supported_features |= SUPPORT_SHELLYRGB_WHITE

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

        key = "brightness"
        if self.wrapper.device.settings.get("mode") == "color":
            key = "gain"

        if self.control_result:
            brightness = self.control_result[key]
        else:
            if key == "brightness":
                brightness = self.block.brightness
            else:
                brightness = self.block.gain
        return int(brightness / 100 * 255)

    @property
    def white_value(self) -> Optional[int]:
        """White value of light."""
        if self.control_result:
            white = self.control_result["white"]
        else:
            white = self.block.white
        return int(white)

    @property
    def hs_color(self):
        """Return the hue and saturation color value of light."""
        if self.control_result:
            red = self.control_result["red"]
            green = self.control_result["green"]
            blue = self.control_result["blue"]
        else:
            red = self.block.red
            green = self.block.green
            blue = self.block.blue
        return color_RGB_to_hs(red, green, blue)

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
            params["brightness"] = params["gain"] = int(tmp_brightness / 255 * 100)
        if ATTR_COLOR_TEMP in kwargs:
            color_temp = color_temperature_mired_to_kelvin(kwargs[ATTR_COLOR_TEMP])
            if color_temp > 6500:
                color_temp = 6500
            elif color_temp < 2700:
                color_temp = 2700
            params["temp"] = int(color_temp)
        if ATTR_HS_COLOR in kwargs:
            red, green, blue = color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            params["red"] = red
            params["green"] = green
            params["blue"] = blue
        if ATTR_WHITE_VALUE in kwargs:
            params["white"] = int(kwargs[ATTR_WHITE_VALUE])
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
