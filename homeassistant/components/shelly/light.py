"""Light for Shelly."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Final, cast

from aioshelly.block_device import Block
import async_timeout

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_TRANSITION,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_ONOFF,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    SUPPORT_EFFECT,
    SUPPORT_TRANSITION,
    LightEntity,
    brightness_supported,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

from . import BlockDeviceWrapper, RpcDeviceWrapper
from .const import (
    AIOSHELLY_DEVICE_TIMEOUT_SEC,
    BLOCK,
    DATA_CONFIG_ENTRY,
    DOMAIN,
    FIRMWARE_PATTERN,
    KELVIN_MAX_VALUE,
    KELVIN_MIN_VALUE_COLOR,
    KELVIN_MIN_VALUE_WHITE,
    LIGHT_TRANSITION_MIN_FIRMWARE_DATE,
    MAX_TRANSITION_TIME,
    MODELS_SUPPORTING_LIGHT_TRANSITION,
    RGBW_MODELS,
    RPC,
    SHBLB_1_RGB_EFFECTS,
    STANDARD_RGB_EFFECTS,
)
from .entity import ShellyBlockEntity, ShellyRpcEntity
from .utils import (
    async_remove_shelly_entity,
    get_device_entry_gen,
    get_rpc_key_ids,
    is_block_channel_type_light,
    is_rpc_channel_type_light,
)

_LOGGER: Final = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lights for device."""
    if get_device_entry_gen(config_entry) == 2:
        return await async_setup_rpc_entry(hass, config_entry, async_add_entities)

    return await async_setup_block_entry(hass, config_entry, async_add_entities)


async def async_setup_block_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entities for block device."""
    wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id][BLOCK]

    blocks = []
    assert wrapper.device.blocks
    for block in wrapper.device.blocks:
        if block.type == "light":
            blocks.append(block)
        elif block.type == "relay":
            if not is_block_channel_type_light(
                wrapper.device.settings, int(block.channel)
            ):
                continue

            blocks.append(block)
            assert wrapper.device.shelly
            unique_id = f"{wrapper.mac}-{block.type}_{block.channel}"
            await async_remove_shelly_entity(hass, "switch", unique_id)

    if not blocks:
        return

    async_add_entities(BlockShellyLight(wrapper, block) for block in blocks)


async def async_setup_rpc_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entities for RPC device."""
    wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id][RPC]
    switch_key_ids = get_rpc_key_ids(wrapper.device.status, "switch")

    switch_ids = []
    for id_ in switch_key_ids:
        if not is_rpc_channel_type_light(wrapper.device.config, id_):
            continue

        switch_ids.append(id_)
        unique_id = f"{wrapper.mac}-switch:{id_}"
        await async_remove_shelly_entity(hass, "switch", unique_id)

    if not switch_ids:
        return

    async_add_entities(RpcShellyLight(wrapper, id_) for id_ in switch_ids)


class BlockShellyLight(ShellyBlockEntity, LightEntity):
    """Entity that controls a light on block based Shelly devices."""

    def __init__(self, wrapper: BlockDeviceWrapper, block: Block) -> None:
        """Initialize light."""
        super().__init__(wrapper, block)
        self.control_result: dict[str, Any] | None = None
        self.mode_result: dict[str, Any] | None = None
        self._supported_color_modes: set[str] = set()
        self._supported_features: int = 0
        self._min_kelvin: int = KELVIN_MIN_VALUE_WHITE
        self._max_kelvin: int = KELVIN_MAX_VALUE

        if hasattr(block, "red") and hasattr(block, "green") and hasattr(block, "blue"):
            self._min_kelvin = KELVIN_MIN_VALUE_COLOR
            if wrapper.model in RGBW_MODELS:
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

        if wrapper.model in MODELS_SUPPORTING_LIGHT_TRANSITION:
            match = FIRMWARE_PATTERN.search(wrapper.device.settings.get("fw", ""))
            if (
                match is not None
                and int(match[0]) >= LIGHT_TRANSITION_MIN_FIRMWARE_DATE
            ):
                self._supported_features |= SUPPORT_TRANSITION

    @property
    def supported_features(self) -> int:
        """Supported features."""
        return self._supported_features

    @property
    def is_on(self) -> bool:
        """If light is on."""
        if self.control_result:
            return cast(bool, self.control_result["ison"])

        return bool(self.block.output)

    @property
    def mode(self) -> str:
        """Return the color mode of the light."""
        if self.mode_result:
            return cast(str, self.mode_result["mode"])

        if hasattr(self.block, "mode"):
            return cast(str, self.block.mode)

        if (
            hasattr(self.block, "red")
            and hasattr(self.block, "green")
            and hasattr(self.block, "blue")
        ):
            return "color"

        return "white"

    @property
    def brightness(self) -> int:
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
    def color_mode(self) -> str:
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
    def color_temp(self) -> int:
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on light."""
        if self.block.type == "relay":
            self.control_result = await self.set_state(turn="on")
            self.async_write_ha_state()
            return

        set_mode = None
        supported_color_modes = self._supported_color_modes
        params: dict[str, Any] = {"turn": "on"}

        if ATTR_TRANSITION in kwargs:
            params["transition"] = min(
                int(kwargs[ATTR_TRANSITION] * 1000), MAX_TRANSITION_TIME
            )

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

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off light."""
        params: dict[str, Any] = {"turn": "off"}

        if ATTR_TRANSITION in kwargs:
            params["transition"] = min(
                int(kwargs[ATTR_TRANSITION] * 1000), MAX_TRANSITION_TIME
            )

        self.control_result = await self.set_state(**params)

        self.async_write_ha_state()

    async def set_light_mode(self, set_mode: str | None) -> bool:
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
    def _update_callback(self) -> None:
        """When device updates, clear control & mode result that overrides state."""
        self.control_result = None
        self.mode_result = None
        super()._update_callback()


class RpcShellyLight(ShellyRpcEntity, LightEntity):
    """Entity that controls a light on RPC based Shelly devices."""

    def __init__(self, wrapper: RpcDeviceWrapper, id_: int) -> None:
        """Initialize light."""
        super().__init__(wrapper, f"switch:{id_}")
        self._id = id_

    @property
    def is_on(self) -> bool:
        """If light is on."""
        return bool(self.wrapper.device.status[self.key]["output"])

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on light."""
        await self.call_rpc("Switch.Set", {"id": self._id, "on": True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off light."""
        await self.call_rpc("Switch.Set", {"id": self._id, "on": False})
