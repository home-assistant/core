"""Light for Shelly."""
from typing import Optional, Tuple

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
from .const import (
    COAP,
    DATA_CONFIG_ENTRY,
    DOMAIN,
    KELVIN_MAX_VALUE,
    KELVIN_MIN_VALUE,
    KELVIN_MIN_VALUE_SHBLB_1,
)
from .entity import ShellyBlockEntity
from .utils import async_remove_shelly_entity


def min_kelvin(model: str):
    """Kelvin (min) for colorTemp."""
    if model in ["SHBLB-1"]:
        return KELVIN_MIN_VALUE_SHBLB_1
    return KELVIN_MIN_VALUE


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
        self.mode_result = None
        self._supported_features = 0

        if hasattr(block, "brightness") or hasattr(block, "gain"):
            self._supported_features |= SUPPORT_BRIGHTNESS
        if hasattr(block, "colorTemp"):
            self._supported_features |= SUPPORT_COLOR_TEMP
        if hasattr(block, "white"):
            self._supported_features |= SUPPORT_WHITE_VALUE
        if hasattr(block, "red") and hasattr(block, "green") and hasattr(block, "blue"):
            self._supported_features |= SUPPORT_COLOR

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
    def mode(self) -> Optional[str]:
        """Return the color mode of the light."""
        if self.mode_result:
            return self.mode_result["mode"]

        if hasattr(self.block, "mode"):
            return self.block.mode

        if (
            hasattr(self.block, "red")
            and hasattr(self.block, "green")
            and hasattr(self.block, "blue")
        ):
            return "color"

        return "white"

    @property
    def brightness(self) -> Optional[int]:
        """Brightness of light."""
        if self.mode == "color":
            if self.control_result:
                brightness = self.control_result["gain"]
            else:
                brightness = self.block.gain
        else:
            if self.control_result:
                brightness = self.control_result["brightness"]
            else:
                brightness = self.block.brightness
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
    def hs_color(self) -> Optional[Tuple[float, float]]:
        """Return the hue and saturation color value of light."""
        if self.mode == "white":
            return color_RGB_to_hs(255, 255, 255)

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
        if self.mode == "color":
            return None

        if self.control_result:
            color_temp = self.control_result["temp"]
        else:
            color_temp = self.block.colorTemp

        # If you set DUO to max mireds in Shelly app, 2700K,
        # It reports 0 temp
        if color_temp == 0:
            return min_kelvin(self.wrapper.model)

        return int(color_temperature_kelvin_to_mired(color_temp))

    @property
    def min_mireds(self) -> Optional[float]:
        """Return the coldest color_temp that this light supports."""
        return color_temperature_kelvin_to_mired(KELVIN_MAX_VALUE)

    @property
    def max_mireds(self) -> Optional[float]:
        """Return the warmest color_temp that this light supports."""
        return color_temperature_kelvin_to_mired(min_kelvin(self.wrapper.model))

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on light."""
        params = {"turn": "on"}
        if ATTR_BRIGHTNESS in kwargs:
            tmp_brightness = int(kwargs[ATTR_BRIGHTNESS] / 255 * 100)
            if hasattr(self.block, "gain"):
                params["gain"] = tmp_brightness
            if hasattr(self.block, "brightness"):
                params["brightness"] = tmp_brightness
        if ATTR_COLOR_TEMP in kwargs:
            color_temp = color_temperature_mired_to_kelvin(kwargs[ATTR_COLOR_TEMP])
            color_temp = min(
                KELVIN_MAX_VALUE, max(min_kelvin(self.wrapper.model), color_temp)
            )
            # Color temperature change - used only in white mode, switch device mode to white
            if self.mode == "color":
                self.mode_result = await self.wrapper.device.switch_light_mode("white")
                params["red"] = params["green"] = params["blue"] = 255
            params["temp"] = int(color_temp)
        elif ATTR_HS_COLOR in kwargs:
            red, green, blue = color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            # Color channels change - used only in color mode, switch device mode to color
            if self.mode == "white":
                self.mode_result = await self.wrapper.device.switch_light_mode("color")
            params["red"] = red
            params["green"] = green
            params["blue"] = blue
        elif ATTR_WHITE_VALUE in kwargs:
            # White channel change - used only in color mode, switch device mode device to color
            if self.mode == "white":
                self.mode_result = await self.wrapper.device.switch_light_mode("color")
            params["white"] = int(kwargs[ATTR_WHITE_VALUE])
        self.control_result = await self.block.set_state(**params)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off light."""
        self.control_result = await self.block.set_state(turn="off")
        self.async_write_ha_state()

    @callback
    def _update_callback(self):
        """When device updates, clear control & mode result that overrides state."""
        self.control_result = None
        self.mode_result = None
        super()._update_callback()
