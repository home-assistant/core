"""Light for Shelly."""

from __future__ import annotations

from typing import Any, cast

from aioshelly.block_device import Block
from aioshelly.const import MODEL_BULB, RPC_GENERATIONS

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    brightness_supported,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    BLOCK_MAX_TRANSITION_TIME_MS,
    DUAL_MODE_LIGHT_MODELS,
    KELVIN_MAX_VALUE,
    KELVIN_MIN_VALUE_COLOR,
    KELVIN_MIN_VALUE_WHITE,
    LOGGER,
    MODELS_SUPPORTING_LIGHT_TRANSITION,
    RGBW_MODELS,
    RPC_MIN_TRANSITION_TIME_SEC,
    SHBLB_1_RGB_EFFECTS,
    STANDARD_RGB_EFFECTS,
)
from .coordinator import ShellyBlockCoordinator, ShellyConfigEntry, ShellyRpcCoordinator
from .entity import ShellyBlockEntity, ShellyRpcEntity
from .utils import (
    async_remove_orphaned_entities,
    async_remove_shelly_entity,
    brightness_to_percentage,
    get_device_entry_gen,
    get_rpc_key_ids,
    is_block_channel_type_light,
    is_rpc_channel_type_light,
    percentage_to_brightness,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up lights for device."""
    if get_device_entry_gen(config_entry) in RPC_GENERATIONS:
        return async_setup_rpc_entry(hass, config_entry, async_add_entities)

    return async_setup_block_entry(hass, config_entry, async_add_entities)


@callback
def async_setup_block_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities for block device."""
    coordinator = config_entry.runtime_data.block
    assert coordinator
    blocks = []
    assert coordinator.device.blocks
    for block in coordinator.device.blocks:
        if block.type == "light":
            blocks.append(block)
        elif block.type == "relay" and block.channel is not None:
            if not is_block_channel_type_light(
                coordinator.device.settings, int(block.channel)
            ):
                continue

            blocks.append(block)
            unique_id = f"{coordinator.mac}-{block.type}_{block.channel}"
            async_remove_shelly_entity(hass, "switch", unique_id)

    if not blocks:
        return

    async_add_entities(BlockShellyLight(coordinator, block) for block in blocks)


@callback
def async_setup_rpc_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities for RPC device."""
    coordinator = config_entry.runtime_data.rpc
    assert coordinator
    switch_key_ids = get_rpc_key_ids(coordinator.device.status, "switch")

    switch_ids = []
    for id_ in switch_key_ids:
        if not is_rpc_channel_type_light(coordinator.device.config, id_):
            continue

        switch_ids.append(id_)
        unique_id = f"{coordinator.mac}-switch:{id_}"
        async_remove_shelly_entity(hass, "switch", unique_id)

    if switch_ids:
        async_add_entities(
            RpcShellySwitchAsLight(coordinator, id_) for id_ in switch_ids
        )
        return

    entities: list[RpcShellyLightBase] = []
    if light_key_ids := get_rpc_key_ids(coordinator.device.status, "light"):
        entities.extend(RpcShellyLight(coordinator, id_) for id_ in light_key_ids)
    if cct_key_ids := get_rpc_key_ids(coordinator.device.status, "cct"):
        entities.extend(RpcShellyCctLight(coordinator, id_) for id_ in cct_key_ids)
    if rgb_key_ids := get_rpc_key_ids(coordinator.device.status, "rgb"):
        entities.extend(RpcShellyRgbLight(coordinator, id_) for id_ in rgb_key_ids)
    if rgbw_key_ids := get_rpc_key_ids(coordinator.device.status, "rgbw"):
        entities.extend(RpcShellyRgbwLight(coordinator, id_) for id_ in rgbw_key_ids)

    async_add_entities(entities)

    async_remove_orphaned_entities(
        hass,
        config_entry.entry_id,
        coordinator.mac,
        LIGHT_DOMAIN,
        coordinator.device.status,
    )


class BlockShellyLight(ShellyBlockEntity, LightEntity):
    """Entity that controls a light on block based Shelly devices."""

    _attr_supported_color_modes: set[str]

    def __init__(self, coordinator: ShellyBlockCoordinator, block: Block) -> None:
        """Initialize light."""
        super().__init__(coordinator, block)
        self.control_result: dict[str, Any] | None = None
        self._attr_supported_color_modes = set()
        self._attr_min_color_temp_kelvin = KELVIN_MIN_VALUE_WHITE
        self._attr_max_color_temp_kelvin = KELVIN_MAX_VALUE

        if hasattr(block, "red") and hasattr(block, "green") and hasattr(block, "blue"):
            self._attr_min_color_temp_kelvin = KELVIN_MIN_VALUE_COLOR
            if coordinator.model in RGBW_MODELS:
                self._attr_supported_color_modes.add(ColorMode.RGBW)
            else:
                self._attr_supported_color_modes.add(ColorMode.RGB)

        if hasattr(block, "colorTemp"):
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)

        if not self._attr_supported_color_modes:
            if hasattr(block, "brightness") or hasattr(block, "gain"):
                self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
            else:
                self._attr_supported_color_modes.add(ColorMode.ONOFF)

        if hasattr(block, "effect"):
            self._attr_supported_features |= LightEntityFeature.EFFECT

        if coordinator.model in MODELS_SUPPORTING_LIGHT_TRANSITION:
            self._attr_supported_features |= LightEntityFeature.TRANSITION

    @property
    def is_on(self) -> bool:
        """If light is on."""
        if self.control_result:
            return cast(bool, self.control_result["ison"])

        return bool(self.block.output)

    @property
    def mode(self) -> str:
        """Return the color mode of the light."""
        if self.control_result and self.control_result.get("mode"):
            return cast(str, self.control_result["mode"])

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
                return percentage_to_brightness(self.control_result["gain"])
            return percentage_to_brightness(cast(int, self.block.gain))

        # white mode
        if self.control_result:
            return percentage_to_brightness(self.control_result["brightness"])
        return percentage_to_brightness(cast(int, self.block.brightness))

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if self.mode == "color":
            if self.coordinator.model in RGBW_MODELS:
                return ColorMode.RGBW
            return ColorMode.RGB

        if hasattr(self.block, "colorTemp"):
            return ColorMode.COLOR_TEMP

        if hasattr(self.block, "brightness") or hasattr(self.block, "gain"):
            return ColorMode.BRIGHTNESS

        return ColorMode.ONOFF

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
        return (cast(int, red), cast(int, green), cast(int, blue))

    @property
    def rgbw_color(self) -> tuple[int, int, int, int]:
        """Return the rgbw color value [int, int, int, int]."""
        if self.control_result:
            white = self.control_result["white"]
        else:
            white = self.block.white

        return (*self.rgb_color, cast(int, white))

    @property
    def color_temp_kelvin(self) -> int:
        """Return the CT color value in kelvin."""
        color_temp = cast(int, self.block.colorTemp)
        if self.control_result:
            color_temp = self.control_result["temp"]

        return min(
            self.max_color_temp_kelvin,
            max(self.min_color_temp_kelvin, color_temp),
        )

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        if self.coordinator.model == MODEL_BULB:
            return list(SHBLB_1_RGB_EFFECTS.values())

        return list(STANDARD_RGB_EFFECTS.values())

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        if self.control_result:
            effect_index = self.control_result["effect"]
        else:
            effect_index = self.block.effect

        if self.coordinator.model == MODEL_BULB:
            return SHBLB_1_RGB_EFFECTS[cast(int, effect_index)]

        return STANDARD_RGB_EFFECTS[cast(int, effect_index)]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on light."""
        if self.block.type == "relay":
            self.control_result = await self.set_state(turn="on")
            self.async_write_ha_state()
            return

        set_mode = None
        supported_color_modes = self._attr_supported_color_modes
        params: dict[str, Any] = {"turn": "on"}

        if ATTR_TRANSITION in kwargs:
            params["transition"] = min(
                int(kwargs[ATTR_TRANSITION] * 1000), BLOCK_MAX_TRANSITION_TIME_MS
            )

        if ATTR_BRIGHTNESS in kwargs and brightness_supported(supported_color_modes):
            if hasattr(self.block, "gain"):
                params["gain"] = brightness_to_percentage(kwargs[ATTR_BRIGHTNESS])
            if hasattr(self.block, "brightness"):
                params["brightness"] = brightness_to_percentage(kwargs[ATTR_BRIGHTNESS])

        if (
            ATTR_COLOR_TEMP_KELVIN in kwargs
            and ColorMode.COLOR_TEMP in supported_color_modes
        ):
            # Color temperature change - used only in white mode,
            # switch device mode to white
            color_temp = kwargs[ATTR_COLOR_TEMP_KELVIN]
            set_mode = "white"
            params["temp"] = int(
                min(
                    self.max_color_temp_kelvin,
                    max(self.min_color_temp_kelvin, color_temp),
                )
            )

        if ATTR_RGB_COLOR in kwargs and ColorMode.RGB in supported_color_modes:
            # Color channels change - used only in color mode,
            # switch device mode to color
            set_mode = "color"
            (params["red"], params["green"], params["blue"]) = kwargs[ATTR_RGB_COLOR]

        if ATTR_RGBW_COLOR in kwargs and ColorMode.RGBW in supported_color_modes:
            # Color channels change - used only in color mode,
            # switch device mode to color
            set_mode = "color"
            (params["red"], params["green"], params["blue"], params["white"]) = kwargs[
                ATTR_RGBW_COLOR
            ]

        if ATTR_EFFECT in kwargs and ATTR_COLOR_TEMP_KELVIN not in kwargs:
            # Color effect change - used only in color mode, switch device mode to color
            set_mode = "color"
            if self.coordinator.model == MODEL_BULB:
                effect_dict = SHBLB_1_RGB_EFFECTS
            else:
                effect_dict = STANDARD_RGB_EFFECTS
            if kwargs[ATTR_EFFECT] in effect_dict.values():
                params["effect"] = [
                    k for k, v in effect_dict.items() if v == kwargs[ATTR_EFFECT]
                ][0]
            else:
                LOGGER.error(
                    "Effect '%s' not supported by device %s",
                    kwargs[ATTR_EFFECT],
                    self.coordinator.model,
                )

        if (
            set_mode
            and set_mode != self.mode
            and self.coordinator.model in DUAL_MODE_LIGHT_MODELS
        ):
            params["mode"] = set_mode

        self.control_result = await self.set_state(**params)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off light."""
        params: dict[str, Any] = {"turn": "off"}

        if ATTR_TRANSITION in kwargs:
            params["transition"] = min(
                int(kwargs[ATTR_TRANSITION] * 1000), BLOCK_MAX_TRANSITION_TIME_MS
            )

        self.control_result = await self.set_state(**params)

        self.async_write_ha_state()

    @callback
    def _update_callback(self) -> None:
        """When device updates, clear control & mode result that overrides state."""
        self.control_result = None
        super()._update_callback()


class RpcShellyLightBase(ShellyRpcEntity, LightEntity):
    """Base Entity for RPC based Shelly devices."""

    _component: str = "Light"

    def __init__(self, coordinator: ShellyRpcCoordinator, id_: int) -> None:
        """Initialize light."""
        super().__init__(coordinator, f"{self._component.lower()}:{id_}")
        self._id = id_

    @property
    def is_on(self) -> bool:
        """If light is on."""
        return bool(self.status["output"])

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return percentage_to_brightness(self.status["brightness"])

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        """Return the rgb color value [int, int, int]."""
        return cast(tuple, self.status["rgb"])

    @property
    def rgbw_color(self) -> tuple[int, int, int, int]:
        """Return the rgbw color value [int, int, int, int]."""
        return (*self.status["rgb"], self.status["white"])

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on light."""
        params: dict[str, Any] = {"id": self._id, "on": True}

        if ATTR_BRIGHTNESS in kwargs:
            params["brightness"] = brightness_to_percentage(kwargs[ATTR_BRIGHTNESS])

        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            params["ct"] = kwargs[ATTR_COLOR_TEMP_KELVIN]

        if ATTR_TRANSITION in kwargs:
            params["transition_duration"] = max(
                kwargs[ATTR_TRANSITION], RPC_MIN_TRANSITION_TIME_SEC
            )

        if ATTR_RGB_COLOR in kwargs:
            params["rgb"] = list(kwargs[ATTR_RGB_COLOR])

        if ATTR_RGBW_COLOR in kwargs:
            params["rgb"] = list(kwargs[ATTR_RGBW_COLOR][:-1])
            params["white"] = kwargs[ATTR_RGBW_COLOR][-1]

        await self.call_rpc(f"{self._component}.Set", params)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off light."""
        params: dict[str, Any] = {"id": self._id, "on": False}

        if ATTR_TRANSITION in kwargs:
            params["transition_duration"] = max(
                kwargs[ATTR_TRANSITION], RPC_MIN_TRANSITION_TIME_SEC
            )

        await self.call_rpc(f"{self._component}.Set", params)


class RpcShellySwitchAsLight(RpcShellyLightBase):
    """Entity that controls a relay as light on RPC based Shelly devices."""

    _component = "Switch"

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}


class RpcShellyLight(RpcShellyLightBase):
    """Entity that controls a light on RPC based Shelly devices."""

    _component = "Light"

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_supported_features = LightEntityFeature.TRANSITION


class RpcShellyCctLight(RpcShellyLightBase):
    """Entity that controls a CCT light on RPC based Shelly devices."""

    _component = "CCT"

    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_supported_features = LightEntityFeature.TRANSITION

    def __init__(self, coordinator: ShellyRpcCoordinator, id_: int) -> None:
        """Initialize light."""
        color_temp_range = coordinator.device.config[f"cct:{id_}"]["ct_range"]
        self._attr_min_color_temp_kelvin = color_temp_range[0]
        self._attr_max_color_temp_kelvin = color_temp_range[1]

        super().__init__(coordinator, id_)

    @property
    def color_temp_kelvin(self) -> int:
        """Return the CT color value in Kelvin."""
        return cast(int, self.status["ct"])


class RpcShellyRgbLight(RpcShellyLightBase):
    """Entity that controls a RGB light on RPC based Shelly devices."""

    _component = "RGB"

    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_supported_features = LightEntityFeature.TRANSITION


class RpcShellyRgbwLight(RpcShellyLightBase):
    """Entity that controls a RGBW light on RPC based Shelly devices."""

    _component = "RGBW"

    _attr_color_mode = ColorMode.RGBW
    _attr_supported_color_modes = {ColorMode.RGBW}
    _attr_supported_features = LightEntityFeature.TRANSITION
