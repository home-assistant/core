"""Light for Shelly."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from aioshelly import Block
import async_timeout

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_ONOFF,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    SUPPORT_EFFECT,
    LightEntity,
    brightness_supported,
)
from homeassistant.core import callback
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

from . import ShellyDeviceWrapper
from .const import (
    AIOSHELLY_DEVICE_TIMEOUT_SEC,
    COAP,
    DATA_CONFIG_ENTRY,
    DOMAIN,
    KELVIN_MAX_VALUE,
    KELVIN_MIN_VALUE_COLOR,
    KELVIN_MIN_VALUE_WHITE,
    SHBLB_1_RGB_EFFECTS,
    STANDARD_RGB_EFFECTS,
)
from .entity import ShellyBlockEntity
from .utils import async_remove_shelly_entity

_LOGGER = logging.getLogger(__name__)


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
        self._supported_color_modes = set()
        self._supported_features = 0
        self._min_kelvin = KELVIN_MIN_VALUE_WHITE
        self._max_kelvin = KELVIN_MAX_VALUE

        if hasattr(block, "red") and hasattr(block, "green") and hasattr(block, "blue"):
            self._min_kelvin = KELVIN_MIN_VALUE_COLOR
            if hasattr(block, "white"):
                self._supported_color_modes.add(COLOR_MODE_RGBW)
            else:
                self._supported_color_modes.add(COLOR_MODE_RGB)

        if hasattr(block, "colorTemp"):
            self._supported_color_modes.add(COLOR_MODE_COLOR_TEMP)

        if not self._supported_color_modes:
            if hasattr(block, "brightness") or hasattr(block, "gain"):
                self._supported_color_modes.add(COLOR_MODE_BRIGHTNESS)
            else:
                self._supported_color_modes.add(COLOR_MODE_ONOFF)

        if hasattr(block, "effect"):
            self._supported_features |= SUPPORT_EFFECT

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
    def mode(self) -> str | None:
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
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        if self.mode == "color":
            if self.control_result:
                brightness_pct = self.control_result["gain"]
            else:
                brightness_pct = self.block.gain
        else:
            if self.control_result:
                brightness_pct = self.control_result["brightness"]
            else:
                brightness_pct = self.block.brightness

        return round(255 * brightness_pct / 100)

    @property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        if self.mode == "color":
            if hasattr(self.block, "white"):
                return COLOR_MODE_RGBW
            return COLOR_MODE_RGB

        if hasattr(self.block, "colorTemp"):
            return COLOR_MODE_COLOR_TEMP

        if hasattr(self.block, "brightness") or hasattr(self.block, "gain"):
            return COLOR_MODE_BRIGHTNESS

        return COLOR_MODE_ONOFF

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        """Return the rgb color value [int, int, int]."""
        if self.control_result:
            red = self.control_result["red"]
            green = self.control_result["green"]
            blue = self.control_result["blue"]
        else:
            red = self.block.red
            green = self.block.green
            blue = self.block.blue
        return (red, green, blue)

    @property
    def rgbw_color(self) -> tuple[int, int, int, int]:
        """Return the rgbw color value [int, int, int, int]."""
        if self.control_result:
            white = self.control_result["white"]
        else:
            white = self.block.white

        return (*self.rgb_color, white)

    @property
    def color_temp(self) -> int | None:
        """Return the CT color value in mireds."""
        if self.control_result:
            color_temp = self.control_result["temp"]
        else:
            color_temp = self.block.colorTemp

        color_temp = min(self._max_kelvin, max(self._min_kelvin, color_temp))

        return int(color_temperature_kelvin_to_mired(color_temp))

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        return int(color_temperature_kelvin_to_mired(self._max_kelvin))

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        return int(color_temperature_kelvin_to_mired(self._min_kelvin))

    @property
    def supported_color_modes(self) -> set | None:
        """Flag supported color modes."""
        return self._supported_color_modes

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        if not self.supported_features & SUPPORT_EFFECT:
            return None

        if self.wrapper.model == "SHBLB-1":
            return list(SHBLB_1_RGB_EFFECTS.values())

        return list(STANDARD_RGB_EFFECTS.values())

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        if not self.supported_features & SUPPORT_EFFECT:
            return None

        if self.control_result:
            effect_index = self.control_result["effect"]
        else:
            effect_index = self.block.effect

        if self.wrapper.model == "SHBLB-1":
            return SHBLB_1_RGB_EFFECTS[effect_index]

        return STANDARD_RGB_EFFECTS[effect_index]

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on light."""
        if self.block.type == "relay":
            self.control_result = await self.set_state(turn="on")
            self.async_write_ha_state()
            return

        set_mode = None
        supported_color_modes = self._supported_color_modes
        params: dict[str, Any] = {"turn": "on"}

        if ATTR_BRIGHTNESS in kwargs and brightness_supported(supported_color_modes):
            brightness_pct = int(100 * (kwargs[ATTR_BRIGHTNESS] + 1) / 255)
            if hasattr(self.block, "gain"):
                params["gain"] = brightness_pct
            if hasattr(self.block, "brightness"):
                params["brightness"] = brightness_pct

        if ATTR_COLOR_TEMP in kwargs and COLOR_MODE_COLOR_TEMP in supported_color_modes:
            color_temp = color_temperature_mired_to_kelvin(kwargs[ATTR_COLOR_TEMP])
            color_temp = min(self._max_kelvin, max(self._min_kelvin, color_temp))
            # Color temperature change - used only in white mode, switch device mode to white
            set_mode = "white"
            params["temp"] = int(color_temp)

        if ATTR_RGB_COLOR in kwargs and COLOR_MODE_RGB in supported_color_modes:
            # Color channels change - used only in color mode, switch device mode to color
            set_mode = "color"
            (params["red"], params["green"], params["blue"]) = kwargs[ATTR_RGB_COLOR]

        if ATTR_RGBW_COLOR in kwargs and COLOR_MODE_RGBW in supported_color_modes:
            # Color channels change - used only in color mode, switch device mode to color
            set_mode = "color"
            (params["red"], params["green"], params["blue"], params["white"]) = kwargs[
                ATTR_RGBW_COLOR
            ]

        if ATTR_EFFECT in kwargs:
            # Color effect change - used only in color mode, switch device mode to color
            set_mode = "color"
            if self.wrapper.model == "SHBLB-1":
                effect_dict = SHBLB_1_RGB_EFFECTS
            else:
                effect_dict = STANDARD_RGB_EFFECTS
            if kwargs[ATTR_EFFECT] in effect_dict.values():
                params["effect"] = [
                    k for k, v in effect_dict.items() if v == kwargs[ATTR_EFFECT]
                ][0]
            else:
                _LOGGER.error(
                    "Effect '%s' not supported by device %s",
                    kwargs[ATTR_EFFECT],
                    self.wrapper.model,
                )

        if await self.set_light_mode(set_mode):
            self.control_result = await self.set_state(**params)

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off light."""
        self.control_result = await self.set_state(turn="off")
        self.async_write_ha_state()

    async def set_light_mode(self, set_mode):
        """Change device mode color/white if mode has changed."""
        if set_mode is None or self.mode == set_mode:
            return True

        _LOGGER.debug("Setting light mode for entity %s, mode: %s", self.name, set_mode)
        try:
            async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
                self.mode_result = await self.wrapper.device.switch_light_mode(set_mode)
        except (asyncio.TimeoutError, OSError) as err:
            _LOGGER.error(
                "Setting light mode for entity %s failed, state: %s, error: %s",
                self.name,
                set_mode,
                repr(err),
            )
            self.wrapper.last_update_success = False
            return False

        return True

    @callback
    def _update_callback(self):
        """When device updates, clear control & mode result that overrides state."""
        self.control_result = None
        self.mode_result = None
        super()._update_callback()
