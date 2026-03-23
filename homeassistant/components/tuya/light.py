"""Support for the Tuya lights."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast

from tuya_device_handlers.device_wrapper.base import DeviceWrapper
from tuya_device_handlers.device_wrapper.common import (
    DPCodeBooleanWrapper,
    DPCodeEnumWrapper,
    DPCodeIntegerWrapper,
)
from tuya_device_handlers.device_wrapper.light import (
    DEFAULT_H_TYPE_V2,
    DEFAULT_S_TYPE_V2,
    DEFAULT_V_TYPE_V2,
    BrightnessWrapper,
    ColorDataWrapper,
    ColorTempWrapper,
)
from tuya_device_handlers.utils import RemapHelper
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_WHITE,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    color_supported,
    filter_supported_color_modes,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.json import json_loads_object

from . import TuyaConfigEntry
from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode, WorkMode
from .entity import TuyaEntity


class FallbackColorDataMode(StrEnum):
    """Fallback color data mode."""

    V1 = "v1"
    """hue: 0-360, saturation: 0-255, value: 0-255"""
    V2 = "v2"
    """hue: 0-360, saturation: 0-1000, value: 0-1000"""


@dataclass(frozen=True)
class TuyaLightEntityDescription(LightEntityDescription):
    """Describe an Tuya light entity."""

    brightness_max: DPCode | None = None
    brightness_min: DPCode | None = None
    brightness: DPCode | tuple[DPCode, ...] | None = None
    color_data: DPCode | tuple[DPCode, ...] | None = None
    color_mode: DPCode | None = None
    color_temp: DPCode | tuple[DPCode, ...] | None = None
    fallback_color_data_mode: FallbackColorDataMode = FallbackColorDataMode.V1


LIGHTS: dict[DeviceCategory, tuple[TuyaLightEntityDescription, ...]] = {
    DeviceCategory.BZYD: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            name=None,
            color_mode=DPCode.WORK_MODE,
            color_data=DPCode.COLOUR_DATA,
        ),
    ),
    DeviceCategory.CLKG: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_BACKLIGHT,
            translation_key="backlight",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.CWWSQ: (
        TuyaLightEntityDescription(
            key=DPCode.LIGHT,
            translation_key="light",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.DC: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            name=None,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_temp=DPCode.TEMP_VALUE,
            color_data=DPCode.COLOUR_DATA,
        ),
    ),
    DeviceCategory.DD: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            name=None,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_temp=DPCode.TEMP_VALUE,
            color_data=DPCode.COLOUR_DATA,
            fallback_color_data_mode=FallbackColorDataMode.V2,
        ),
    ),
    DeviceCategory.DJ: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            name=None,
            color_mode=DPCode.WORK_MODE,
            brightness=(DPCode.BRIGHT_VALUE_V2, DPCode.BRIGHT_VALUE),
            color_temp=(DPCode.TEMP_VALUE_V2, DPCode.TEMP_VALUE),
            color_data=(DPCode.COLOUR_DATA_V2, DPCode.COLOUR_DATA),
        ),
        # Not documented
        # Based on multiple reports: manufacturer customized Dimmer 2 switches
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="indexed_light",
            translation_placeholders={"index": "1"},
            brightness=DPCode.BRIGHT_VALUE_1,
        ),
    ),
    DeviceCategory.DSD: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            name=None,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
        ),
    ),
    DeviceCategory.FS: (
        TuyaLightEntityDescription(
            key=DPCode.LIGHT,
            name=None,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_temp=DPCode.TEMP_VALUE,
        ),
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            translation_key="indexed_light",
            translation_placeholders={"index": "2"},
            brightness=DPCode.BRIGHT_VALUE_1,
        ),
    ),
    DeviceCategory.FSD: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            name=None,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_temp=DPCode.TEMP_VALUE,
            color_data=DPCode.COLOUR_DATA,
        ),
        # Some ceiling fan lights use LIGHT for DPCode instead of SWITCH_LED
        TuyaLightEntityDescription(
            key=DPCode.LIGHT,
            name=None,
        ),
    ),
    DeviceCategory.FWD: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            name=None,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_temp=DPCode.TEMP_VALUE,
            color_data=DPCode.COLOUR_DATA,
        ),
    ),
    DeviceCategory.GYD: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            name=None,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_temp=DPCode.TEMP_VALUE,
            color_data=DPCode.COLOUR_DATA,
        ),
    ),
    DeviceCategory.HXD: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            translation_key="light",
            brightness=(DPCode.BRIGHT_VALUE_V2, DPCode.BRIGHT_VALUE),
            brightness_max=DPCode.BRIGHTNESS_MAX_1,
            brightness_min=DPCode.BRIGHTNESS_MIN_1,
        ),
    ),
    DeviceCategory.JSQ: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            name=None,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_data=DPCode.COLOUR_DATA_HSV,
        ),
    ),
    DeviceCategory.KG: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_BACKLIGHT,
            translation_key="backlight",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.KJ: (
        TuyaLightEntityDescription(
            key=DPCode.LIGHT,
            translation_key="backlight",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.KT: (
        TuyaLightEntityDescription(
            key=DPCode.LIGHT,
            translation_key="backlight",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.KS: (
        TuyaLightEntityDescription(
            key=DPCode.LIGHT,
            translation_key="backlight",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.MBD: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            name=None,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_data=DPCode.COLOUR_DATA,
        ),
    ),
    DeviceCategory.MSP: (
        TuyaLightEntityDescription(
            key=DPCode.LIGHT,
            translation_key="light",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.QJDCZ: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            name=None,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_data=DPCode.COLOUR_DATA,
        ),
    ),
    DeviceCategory.QN: (
        TuyaLightEntityDescription(
            key=DPCode.LIGHT,
            translation_key="backlight",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SP: (
        TuyaLightEntityDescription(
            key=DPCode.FLOODLIGHT_SWITCH,
            brightness=DPCode.FLOODLIGHT_LIGHTNESS,
            name="Floodlight",
        ),
        TuyaLightEntityDescription(
            key=DPCode.BASIC_INDICATOR,
            name="Indicator light",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    DeviceCategory.SZ: (
        TuyaLightEntityDescription(
            key=DPCode.LIGHT,
            brightness=DPCode.BRIGHT_VALUE,
            translation_key="light",
        ),
    ),
    DeviceCategory.TGKG: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED_1,
            translation_key="indexed_light",
            translation_placeholders={"index": "1"},
            brightness=DPCode.BRIGHT_VALUE_1,
            brightness_max=DPCode.BRIGHTNESS_MAX_1,
            brightness_min=DPCode.BRIGHTNESS_MIN_1,
        ),
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED_2,
            translation_key="indexed_light",
            translation_placeholders={"index": "2"},
            brightness=DPCode.BRIGHT_VALUE_2,
            brightness_max=DPCode.BRIGHTNESS_MAX_2,
            brightness_min=DPCode.BRIGHTNESS_MIN_2,
        ),
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED_3,
            translation_key="indexed_light",
            translation_placeholders={"index": "3"},
            brightness=DPCode.BRIGHT_VALUE_3,
            brightness_max=DPCode.BRIGHTNESS_MAX_3,
            brightness_min=DPCode.BRIGHTNESS_MIN_3,
        ),
    ),
    DeviceCategory.TGQ: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            translation_key="light",
            brightness=(DPCode.BRIGHT_VALUE_V2, DPCode.BRIGHT_VALUE),
            brightness_max=DPCode.BRIGHTNESS_MAX_1,
            brightness_min=DPCode.BRIGHTNESS_MIN_1,
        ),
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED_1,
            translation_key="indexed_light",
            translation_placeholders={"index": "1"},
            brightness=DPCode.BRIGHT_VALUE_1,
        ),
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED_2,
            translation_key="indexed_light",
            translation_placeholders={"index": "2"},
            brightness=DPCode.BRIGHT_VALUE_2,
        ),
    ),
    DeviceCategory.TYD: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            name=None,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_temp=DPCode.TEMP_VALUE,
            color_data=DPCode.COLOUR_DATA,
        ),
    ),
    DeviceCategory.TYNDJ: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            name=None,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_temp=DPCode.TEMP_VALUE,
            color_data=DPCode.COLOUR_DATA,
        ),
    ),
    DeviceCategory.XDD: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            name=None,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_temp=DPCode.TEMP_VALUE,
            color_data=DPCode.COLOUR_DATA,
        ),
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_NIGHT_LIGHT,
            translation_key="night_light",
        ),
    ),
    DeviceCategory.YKQ: (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_CONTROLLER,
            name=None,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_CONTROLLER,
            color_temp=DPCode.TEMP_CONTROLLER,
        ),
    ),
}

# Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
LIGHTS[DeviceCategory.CZ] = LIGHTS[DeviceCategory.KG]

# Power Socket (duplicate of `kg`)
LIGHTS[DeviceCategory.PC] = LIGHTS[DeviceCategory.KG]

# Smart Camera - Low power consumption camera (duplicate of `sp`)
LIGHTS[DeviceCategory.DGHSXJ] = LIGHTS[DeviceCategory.SP]

# Dimmer (duplicate of `tgq`)
LIGHTS[DeviceCategory.TDQ] = LIGHTS[DeviceCategory.TGQ]


def _get_brightness_wrapper(
    device: CustomerDevice, description: TuyaLightEntityDescription
) -> BrightnessWrapper | None:
    if (
        brightness_wrapper := BrightnessWrapper.find_dpcode(
            device, description.brightness, prefer_function=True
        )
    ) is None:
        return None
    if brightness_max := DPCodeIntegerWrapper.find_dpcode(
        device, description.brightness_max, prefer_function=True
    ):
        brightness_wrapper.brightness_max = brightness_max
        brightness_wrapper.brightness_max_remap = RemapHelper.from_type_information(
            brightness_max.type_information, 0, 255
        )
    if brightness_min := DPCodeIntegerWrapper.find_dpcode(
        device, description.brightness_min, prefer_function=True
    ):
        brightness_wrapper.brightness_min = brightness_min
        brightness_wrapper.brightness_min_remap = RemapHelper.from_type_information(
            brightness_min.type_information, 0, 255
        )
    return brightness_wrapper


def _get_color_data_wrapper(
    device: CustomerDevice,
    description: TuyaLightEntityDescription,
    brightness_wrapper: BrightnessWrapper | None,
) -> ColorDataWrapper | None:
    if (
        color_data_wrapper := ColorDataWrapper.find_dpcode(
            device, description.color_data, prefer_function=True
        )
    ) is None:
        return None

    # Fetch color data type information
    if function_data := json_loads_object(
        color_data_wrapper.type_information.type_data
    ):
        color_data_wrapper.h_type = RemapHelper.from_function_data(
            cast(dict, function_data["h"]), 0, 360
        )
        color_data_wrapper.s_type = RemapHelper.from_function_data(
            cast(dict, function_data["s"]), 0, 100
        )
        color_data_wrapper.v_type = RemapHelper.from_function_data(
            cast(dict, function_data["v"]), 0, 255
        )
    elif (
        description.fallback_color_data_mode == FallbackColorDataMode.V2
        or color_data_wrapper.dpcode == DPCode.COLOUR_DATA_V2
        or (brightness_wrapper and brightness_wrapper.max_value > 255)
    ):
        color_data_wrapper.h_type = DEFAULT_H_TYPE_V2
        color_data_wrapper.s_type = DEFAULT_S_TYPE_V2
        color_data_wrapper.v_type = DEFAULT_V_TYPE_V2

    return color_data_wrapper


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up tuya light dynamically through tuya discovery."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]):
        """Discover and add a discovered tuya light."""
        entities: list[TuyaLightEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if descriptions := LIGHTS.get(device.category):
                entities.extend(
                    TuyaLightEntity(
                        device,
                        manager,
                        description,
                        brightness_wrapper=(
                            brightness_wrapper := _get_brightness_wrapper(
                                device, description
                            )
                        ),
                        color_data_wrapper=_get_color_data_wrapper(
                            device, description, brightness_wrapper
                        ),
                        color_mode_wrapper=DPCodeEnumWrapper.find_dpcode(
                            device, description.color_mode, prefer_function=True
                        ),
                        color_temp_wrapper=ColorTempWrapper.find_dpcode(
                            device, description.color_temp, prefer_function=True
                        ),
                        switch_wrapper=switch_wrapper,
                    )
                    for description in descriptions
                    if (
                        switch_wrapper := DPCodeBooleanWrapper.find_dpcode(
                            device, description.key, prefer_function=True
                        )
                    )
                )

        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaLightEntity(TuyaEntity, LightEntity):
    """Tuya light device."""

    entity_description: TuyaLightEntityDescription

    _white_color_mode = ColorMode.COLOR_TEMP
    _fixed_color_mode: ColorMode | None = None
    _attr_min_color_temp_kelvin = 2000  # 500 Mireds
    _attr_max_color_temp_kelvin = 6500  # 153 Mireds

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaLightEntityDescription,
        *,
        brightness_wrapper: DeviceWrapper[int] | None,
        color_data_wrapper: DeviceWrapper[tuple[float, float, float]] | None,
        color_mode_wrapper: DeviceWrapper[str] | None,
        color_temp_wrapper: DeviceWrapper[int] | None,
        switch_wrapper: DeviceWrapper[bool],
    ) -> None:
        """Init TuyaHaLight."""
        super().__init__(device, device_manager, description)
        self._brightness_wrapper = brightness_wrapper
        self._color_data_wrapper = color_data_wrapper
        self._color_mode_wrapper = color_mode_wrapper
        self._color_temp_wrapper = color_temp_wrapper
        self._switch_wrapper = switch_wrapper

        color_modes: set[ColorMode] = {ColorMode.ONOFF}

        if brightness_wrapper:
            color_modes.add(ColorMode.BRIGHTNESS)

        if color_data_wrapper:
            color_modes.add(ColorMode.HS)

        # Check if the light has color temperature
        if color_temp_wrapper:
            color_modes.add(ColorMode.COLOR_TEMP)
        # If light has color but does not have color_temp, check if it has
        # work_mode "white"
        elif (
            color_supported(color_modes)
            and color_mode_wrapper is not None
            and WorkMode.WHITE in color_mode_wrapper.options
        ):
            color_modes.add(ColorMode.WHITE)
            self._white_color_mode = ColorMode.WHITE

        self._attr_supported_color_modes = filter_supported_color_modes(color_modes)
        if len(self._attr_supported_color_modes) == 1:
            # If the light supports only a single color mode, set it now
            self._fixed_color_mode = next(iter(self._attr_supported_color_modes))

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._read_wrapper(self._switch_wrapper)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on or control the light."""
        commands = self._switch_wrapper.get_update_commands(self.device, True)

        if self._color_mode_wrapper and (
            ATTR_WHITE in kwargs or ATTR_COLOR_TEMP_KELVIN in kwargs
        ):
            commands.extend(
                self._color_mode_wrapper.get_update_commands(
                    self.device, WorkMode.WHITE
                ),
            )

        if self._color_temp_wrapper and ATTR_COLOR_TEMP_KELVIN in kwargs:
            commands.extend(
                self._color_temp_wrapper.get_update_commands(
                    self.device, kwargs[ATTR_COLOR_TEMP_KELVIN]
                )
            )

        if self._color_data_wrapper and (
            ATTR_HS_COLOR in kwargs
            or (
                ATTR_BRIGHTNESS in kwargs
                and self.color_mode == ColorMode.HS
                and ATTR_WHITE not in kwargs
                and ATTR_COLOR_TEMP_KELVIN not in kwargs
            )
        ):
            if self._color_mode_wrapper:
                commands.extend(
                    self._color_mode_wrapper.get_update_commands(
                        self.device, WorkMode.COLOUR
                    ),
                )

            if not (brightness := kwargs.get(ATTR_BRIGHTNESS)):
                brightness = self.brightness or 0

            if not (color := kwargs.get(ATTR_HS_COLOR)):
                color = self.hs_color or (0, 0)

            commands.extend(
                self._color_data_wrapper.get_update_commands(
                    self.device, (color[0], color[1], brightness)
                ),
            )

        elif self._brightness_wrapper and (
            ATTR_BRIGHTNESS in kwargs or ATTR_WHITE in kwargs
        ):
            if ATTR_BRIGHTNESS in kwargs:
                brightness = kwargs[ATTR_BRIGHTNESS]
            else:
                brightness = kwargs[ATTR_WHITE]

            commands.extend(
                self._brightness_wrapper.get_update_commands(self.device, brightness),
            )

        await self._async_send_commands(commands)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self._async_send_wrapper_updates(self._switch_wrapper, False)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        # If the light is currently in color mode, extract the brightness from the color data
        if self.color_mode == ColorMode.HS and self._color_data_wrapper:
            hsv_data = self._read_wrapper(self._color_data_wrapper)
            return None if hsv_data is None else round(hsv_data[2])

        return self._read_wrapper(self._brightness_wrapper)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature value in Kelvin."""
        return self._read_wrapper(self._color_temp_wrapper)

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs_color of the light."""
        if self._color_data_wrapper is None:
            return None
        hsv_data = self._read_wrapper(self._color_data_wrapper)
        return None if hsv_data is None else (hsv_data[0], hsv_data[1])

    @property
    def color_mode(self) -> ColorMode:
        """Return the color_mode of the light."""
        if self._fixed_color_mode:
            # The light supports only a single color mode, return it
            return self._fixed_color_mode

        # The light supports both white (with or without adjustable color temperature)
        # and HS, determine which mode the light is in. We consider it to be in HS color
        # mode, when work mode is anything else than "white".
        if (
            self._color_mode_wrapper
            and self._read_wrapper(self._color_mode_wrapper) != WorkMode.WHITE
        ):
            return ColorMode.HS
        return self._white_color_mode
