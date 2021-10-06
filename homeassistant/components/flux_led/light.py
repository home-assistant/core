"""Support for FluxLED/MagicHome lights."""
from __future__ import annotations

import ast
from functools import partial
import logging
import random
from typing import Any, Final, cast

from flux_led import WifiLedBulb
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_WHITE,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    COLOR_MODE_ONOFF,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    COLOR_MODE_RGBWW,
    COLOR_MODE_WHITE,
    EFFECT_COLORLOOP,
    EFFECT_RANDOM,
    PLATFORM_SCHEMA,
    SUPPORT_EFFECT,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.const import (
    ATTR_MANUFACTURER,
    ATTR_MODE,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_DEVICES,
    CONF_HOST,
    CONF_MAC,
    CONF_MODE,
    CONF_NAME,
    CONF_PROTOCOL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.color as color_util

from . import FluxLedUpdateCoordinator
from .const import (
    CONF_AUTOMATIC_ADD,
    CONF_COLORS,
    CONF_CUSTOM_EFFECT,
    CONF_CUSTOM_EFFECT_COLORS,
    CONF_CUSTOM_EFFECT_SPEED_PCT,
    CONF_CUSTOM_EFFECT_TRANSITION,
    CONF_SPEED_PCT,
    CONF_TRANSITION,
    DEFAULT_EFFECT_SPEED,
    DOMAIN,
    FLUX_HOST,
    FLUX_LED_DISCOVERY,
    FLUX_MAC,
    MODE_AUTO,
    MODE_CCT,
    MODE_DIM,
    MODE_RGB,
    MODE_RGBW,
    MODE_RGBWW,
    MODE_WHITE,
    TRANSITION_GRADUAL,
    TRANSITION_JUMP,
    TRANSITION_STROBE,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLUX_LED: Final = SUPPORT_EFFECT | SUPPORT_TRANSITION

FLUX_COLOR_MODE_TO_HASS: Final = {
    MODE_RGB: COLOR_MODE_HS,
    MODE_RGBW: COLOR_MODE_RGBW,
    MODE_RGBWW: COLOR_MODE_RGBWW,
    MODE_CCT: COLOR_MODE_COLOR_TEMP,
    MODE_DIM: COLOR_MODE_WHITE,
}

# Constant color temp values for 2 flux_led special modes
# Warm-white and Cool-white modes
COLOR_TEMP_WARM_VS_COLD_WHITE_CUT_OFF: Final = 285

# List of supported effects which aren't already declared in LIGHT
EFFECT_RED_FADE: Final = "red_fade"
EFFECT_GREEN_FADE: Final = "green_fade"
EFFECT_BLUE_FADE: Final = "blue_fade"
EFFECT_YELLOW_FADE: Final = "yellow_fade"
EFFECT_CYAN_FADE: Final = "cyan_fade"
EFFECT_PURPLE_FADE: Final = "purple_fade"
EFFECT_WHITE_FADE: Final = "white_fade"
EFFECT_RED_GREEN_CROSS_FADE: Final = "rg_cross_fade"
EFFECT_RED_BLUE_CROSS_FADE: Final = "rb_cross_fade"
EFFECT_GREEN_BLUE_CROSS_FADE: Final = "gb_cross_fade"
EFFECT_COLORSTROBE: Final = "colorstrobe"
EFFECT_RED_STROBE: Final = "red_strobe"
EFFECT_GREEN_STROBE: Final = "green_strobe"
EFFECT_BLUE_STROBE: Final = "blue_strobe"
EFFECT_YELLOW_STROBE: Final = "yellow_strobe"
EFFECT_CYAN_STROBE: Final = "cyan_strobe"
EFFECT_PURPLE_STROBE: Final = "purple_strobe"
EFFECT_WHITE_STROBE: Final = "white_strobe"
EFFECT_COLORJUMP: Final = "colorjump"
EFFECT_CUSTOM: Final = "custom"

EFFECT_MAP: Final = {
    EFFECT_COLORLOOP: 0x25,
    EFFECT_RED_FADE: 0x26,
    EFFECT_GREEN_FADE: 0x27,
    EFFECT_BLUE_FADE: 0x28,
    EFFECT_YELLOW_FADE: 0x29,
    EFFECT_CYAN_FADE: 0x2A,
    EFFECT_PURPLE_FADE: 0x2B,
    EFFECT_WHITE_FADE: 0x2C,
    EFFECT_RED_GREEN_CROSS_FADE: 0x2D,
    EFFECT_RED_BLUE_CROSS_FADE: 0x2E,
    EFFECT_GREEN_BLUE_CROSS_FADE: 0x2F,
    EFFECT_COLORSTROBE: 0x30,
    EFFECT_RED_STROBE: 0x31,
    EFFECT_GREEN_STROBE: 0x32,
    EFFECT_BLUE_STROBE: 0x33,
    EFFECT_YELLOW_STROBE: 0x34,
    EFFECT_CYAN_STROBE: 0x35,
    EFFECT_PURPLE_STROBE: 0x36,
    EFFECT_WHITE_STROBE: 0x37,
    EFFECT_COLORJUMP: 0x38,
}
EFFECT_ID_NAME: Final = {v: k for k, v in EFFECT_MAP.items()}
EFFECT_CUSTOM_CODE: Final = 0x60

WHITE_MODES: Final = {MODE_RGBW}

FLUX_EFFECT_LIST: Final = sorted(EFFECT_MAP) + [EFFECT_RANDOM]

SERVICE_CUSTOM_EFFECT: Final = "set_custom_effect"

CUSTOM_EFFECT_DICT: Final = {
    vol.Required(CONF_COLORS): vol.All(
        cv.ensure_list,
        vol.Length(min=1, max=16),
        [vol.All(vol.ExactSequence((cv.byte, cv.byte, cv.byte)), vol.Coerce(tuple))],
    ),
    vol.Optional(CONF_SPEED_PCT, default=50): vol.All(
        vol.Range(min=0, max=100), vol.Coerce(int)
    ),
    vol.Optional(CONF_TRANSITION, default=TRANSITION_GRADUAL): vol.All(
        cv.string, vol.In([TRANSITION_GRADUAL, TRANSITION_JUMP, TRANSITION_STROBE])
    ),
}

CUSTOM_EFFECT_SCHEMA: Final = vol.Schema(CUSTOM_EFFECT_DICT)

DEVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(ATTR_MODE, default=MODE_AUTO): vol.All(
            cv.string, vol.In([MODE_AUTO, MODE_RGBW, MODE_RGB, MODE_WHITE])
        ),
        vol.Optional(CONF_PROTOCOL): vol.All(cv.string, vol.In(["ledenet"])),
        vol.Optional(CONF_CUSTOM_EFFECT): CUSTOM_EFFECT_SCHEMA,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
        vol.Optional(CONF_AUTOMATIC_ADD, default=False): cv.boolean,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up the flux led platform."""
    domain_data = hass.data[DOMAIN]
    discovered_mac_by_host = {
        device[FLUX_HOST]: device[FLUX_MAC]
        for device in domain_data[FLUX_LED_DISCOVERY]
    }
    for host, device_config in config.get(CONF_DEVICES, {}).items():
        _LOGGER.warning(
            "Configuring flux_led via yaml is deprecated; the configuration for"
            " %s has been migrated to a config entry and can be safely removed",
            host,
        )
        custom_effects = device_config.get(CONF_CUSTOM_EFFECT, {})
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data={
                    CONF_HOST: host,
                    CONF_MAC: discovered_mac_by_host.get(host),
                    CONF_NAME: device_config[CONF_NAME],
                    CONF_PROTOCOL: device_config.get(CONF_PROTOCOL),
                    CONF_MODE: device_config.get(ATTR_MODE, MODE_AUTO),
                    CONF_CUSTOM_EFFECT_COLORS: str(custom_effects.get(CONF_COLORS)),
                    CONF_CUSTOM_EFFECT_SPEED_PCT: custom_effects.get(
                        CONF_SPEED_PCT, DEFAULT_EFFECT_SPEED
                    ),
                    CONF_CUSTOM_EFFECT_TRANSITION: custom_effects.get(
                        CONF_TRANSITION, TRANSITION_GRADUAL
                    ),
                },
            )
        )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flux lights."""
    coordinator: FluxLedUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_CUSTOM_EFFECT,
        CUSTOM_EFFECT_DICT,
        "set_custom_effect",
    )
    options = entry.options

    try:
        custom_effect_colors = ast.literal_eval(
            options.get(CONF_CUSTOM_EFFECT_COLORS) or "[]"
        )
    except (ValueError, TypeError, SyntaxError, MemoryError) as ex:
        _LOGGER.warning(
            "Could not parse custom effect colors for %s: %s", entry.unique_id, ex
        )
        custom_effect_colors = []

    async_add_entities(
        [
            FluxLight(
                coordinator,
                entry.unique_id,
                entry.data[CONF_NAME],
                options.get(CONF_MODE) or MODE_AUTO,
                list(custom_effect_colors),
                options.get(CONF_CUSTOM_EFFECT_SPEED_PCT, DEFAULT_EFFECT_SPEED),
                options.get(CONF_CUSTOM_EFFECT_TRANSITION, TRANSITION_GRADUAL),
            )
        ]
    )


class FluxLight(CoordinatorEntity, LightEntity):
    """Representation of a Flux light."""

    coordinator: FluxLedUpdateCoordinator

    def __init__(
        self,
        coordinator: FluxLedUpdateCoordinator,
        unique_id: str | None,
        name: str,
        mode: str,
        custom_effect_colors: list[tuple[int, int, int]],
        custom_effect_speed_pct: int,
        custom_effect_transition: str,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._bulb: WifiLedBulb = coordinator.device
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._ip_address = coordinator.host
        self._mode = mode
        self._color_temp_mired = None
        self._rgbww = None
        self._custom_effect_colors = custom_effect_colors
        self._custom_effect_speed_pct = custom_effect_speed_pct
        self._custom_effect_transition = custom_effect_transition
        old_protocol = self._bulb.protocol == "LEDENET_ORIGINAL"
        if self.unique_id:
            self._attr_device_info = {
                "connections": {(dr.CONNECTION_NETWORK_MAC, self.unique_id)},
                ATTR_MODEL: f"0x{self._bulb.raw_state[1]:02X}",
                ATTR_SW_VERSION: "1" if old_protocol else str(self._bulb.raw_state[10]),
                ATTR_NAME: self.name,
                ATTR_MANUFACTURER: "FluxLED/Magic Home",
            }

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return cast(bool, self._bulb.is_on)

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        raw_state = self._bulb.raw_state
        if self.color_mode == COLOR_MODE_RGBWW:
            white_brightness = (raw_state.warm_white + raw_state.cool_white) / 2
            brightness = (self._color_brightness + white_brightness) / 2
        elif self.color_mode == COLOR_MODE_RGBW:
            brightness = (self._color_brightness + raw_state.warm_white) / 2
        elif self.color_mode == COLOR_MODE_HS:
            brightness = self._color_brightness
        elif self.color_mode == COLOR_MODE_COLOR_TEMP:
            _, brightness = self._bulb.getWhiteTemperature()
        elif self.color_mode == COLOR_MODE_WHITE:
            brightness = raw_state.warm_white
        return int(round(brightness, 0))

    @property
    def _color_brightness(self) -> int:
        """Get the color brightness."""
        raw_state = self._bulb.raw_state
        _, _, v = color_util.color_RGB_to_hsv(
            raw_state.red, raw_state.green, raw_state.blue
        )
        return int(round(v * 2.55, 0))

    @property
    def color_temp(self) -> int:
        """Return the kelvin value of this light in mired."""
        return color_util.color_temperature_kelvin_to_mired(self._color_temp_kelvin)

    @property
    def _color_temp_kelvin(self) -> int:
        """Return the kelvin value of this light in Kelvin."""
        t, _ = self._bulb.getWhiteTemperature()
        return cast(int, t)

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs color value [float, float]."""
        raw_state = self._bulb.raw_state
        return color_util.color_RGB_to_hs(
            raw_state.red,
            raw_state.green,
            raw_state.blue,
        )

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the rgbw color value [int, int, int, int]."""
        raw_state = self._bulb.raw_state
        return (
            raw_state.red,
            raw_state.green,
            raw_state.blue,
            raw_state.warm_white,
        )

    @property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return the rgbww color value [int, int, int, int, int]."""
        raw_state = self._bulb.raw_state
        return (
            raw_state.red,
            raw_state.green,
            raw_state.blue,
            raw_state.warm_white,
            raw_state.cool_white,
        )

    @property
    def supported_color_modes(self) -> set[str]:
        """Flag supported color modes."""
        mode_list = {COLOR_MODE_ONOFF, COLOR_MODE_BRIGHTNESS}
        for mode in self._bulb.color_modes:
            mode_list.add(FLUX_COLOR_MODE_TO_HASS[mode])
        return mode_list

    @property
    def color_mode(self) -> str:
        """Return the color mode of the light."""
        return FLUX_COLOR_MODE_TO_HASS.get(self._bulb.color_mode, COLOR_MODE_BRIGHTNESS)

    @property
    def effect_list(self) -> list[str]:
        """Return the list of supported effects."""
        if self._custom_effect_colors:
            return FLUX_EFFECT_LIST + [EFFECT_CUSTOM]
        return FLUX_EFFECT_LIST

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        if (current_mode := self._bulb.raw_state[3]) == EFFECT_CUSTOM_CODE:
            return EFFECT_CUSTOM
        return EFFECT_ID_NAME.get(current_mode)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the attributes."""
        # Values added for testing only, remove before merging
        return {
            "ip_address": self._ip_address,
            "model_num": hex(self._bulb.model_num),
            "brightness_pct": str(round(self.brightness / 255 * 100, 0)),
            "test_color_mode": self.color_mode,
            "test_supported_color_modes": self.supported_color_modes,
            "mode": hex(self._bulb.raw_state.mode),
            "preset_pattern": hex(self._bulb.raw_state.preset_pattern),
            "internal_color_modes": self._bulb.color_modes,
            "internal_color_mode": self._bulb.color_mode,
            "hex_color_mode": hex(self._bulb.raw_state.color_mode),
            "red": self._bulb.raw_state.red,
            "green": self._bulb.raw_state.green,
            "blue": self._bulb.raw_state.blue,
            "warm_white": self._bulb.raw_state.warm_white,
            "cool_white": self._bulb.raw_state.cool_white,
        }

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        return cast(int, 154)

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        return cast(int, 370)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the specified or all lights on."""
        await self.hass.async_add_executor_job(partial(self._turn_on, **kwargs))
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _turn_on(self, **kwargs: Any) -> None:
        """Turn the specified or all lights on."""
        _LOGGER.warning(
            "Calling turn_on for %s with current color mode: %s with kwargs: %s",
            self._bulb.ipaddr,
            self.color_mode,
            kwargs,
        )
        if not self.is_on:
            self._bulb.turnOn()
            if not kwargs:
                return

        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is None:
            brightness = self.brightness

        # Handle switch to CCT Color Mode
        if ATTR_COLOR_TEMP in kwargs:
            color_temp_mired = kwargs[ATTR_COLOR_TEMP]
            color_temp_kelvin = color_util.color_temperature_mired_to_kelvin(
                color_temp_mired
            )
            self._bulb.setWhiteTemperature(color_temp_kelvin, brightness)
            return
        # Handle switch to HS Color Mode
        if ATTR_HS_COLOR in kwargs:
            self._bulb.setRgbw(
                *color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR]),
                brightness=brightness,
            )
            return
        # Handle switch to RGBW Color Mode
        if ATTR_RGBW_COLOR in kwargs:
            if ATTR_BRIGHTNESS in kwargs:
                rgbw, _ = self.RGBWW_brightness(kwargs[ATTR_RGBW_COLOR], brightness)
            else:
                rgbw = kwargs[ATTR_RGBW_COLOR]
            self._bulb.setRgbw(*rgbw)
            return
        # Handle switch to RGBWW Color Mode
        if ATTR_RGBWW_COLOR in kwargs:
            if ATTR_BRIGHTNESS in kwargs:
                rgbww, _ = self.RGBWW_brightness(kwargs[ATTR_RGBWW_COLOR], brightness)
            else:
                rgbww = kwargs[ATTR_RGBWW_COLOR]
            self._bulb.setRgbw(*rgbww[0:4], w2=rgbww[4])
            return
        # Handle switch to White Color Mode
        if ATTR_WHITE in kwargs:
            self._bulb.setWarmWhite255(kwargs[ATTR_WHITE])
            return
        if ATTR_EFFECT in kwargs:
            effect = kwargs[ATTR_EFFECT]
            # Random color effect
            if effect == EFFECT_RANDOM:
                self._bulb.setRgb(
                    random.randint(0, 255),
                    random.randint(0, 255),
                    random.randint(0, 255),
                )
                return

            # Custom effect
            if effect == EFFECT_CUSTOM:
                if self._custom_effect_colors:
                    self._bulb.setCustomPattern(
                        self._custom_effect_colors,
                        self._custom_effect_speed_pct,
                        self._custom_effect_transition,
                    )
                return

            # Effect selection
            if effect in EFFECT_MAP:
                self._bulb.setPresetPattern(EFFECT_MAP[effect], DEFAULT_EFFECT_SPEED)
                return

            return

        # Handle brightness adjustment in CCT Color Mode
        if self.color_mode == COLOR_MODE_COLOR_TEMP:
            self._bulb.setWhiteTemperature(self._color_temp_kelvin, brightness)
            return
        # Handle brightness adjustment in RGB Color Mode
        if self.color_mode == COLOR_MODE_HS:
            self._bulb.setRgbw(
                *color_util.color_hs_to_RGB(*self.hs_color), brightness=brightness
            )
            return
        # Handle brightness adjustment in RGBW Color Mode
        if self.color_mode == COLOR_MODE_RGBW:
            rgbw, _ = self.RGBWW_brightness(self.rgbw_color, brightness)
            self._bulb.setRgbw(*rgbw)
            return
        # Handle brightness adjustment in RGBWW Color Mode
        if self.color_mode == COLOR_MODE_RGBWW:
            rgbww, _ = self.RGBWW_brightness(self.rgbww_color, brightness)
            self._bulb.setRgbw(*rgbww[0:4], w2=rgbww[4])
            return
        # Handle White Color Mode
        if self.color_mode == COLOR_MODE_WHITE:
            self._bulb.setWarmWhite255(brightness)
            return
        # Handle Brightness Only Color Mode
        if self.color_mode == COLOR_MODE_BRIGHTNESS:
            self._bulb.setWarmWhite255(brightness)
            return

    def set_custom_effect(
        self, colors: list[tuple[int, int, int]], speed_pct: int, transition: str
    ) -> None:
        """Set a custom effect on the bulb."""
        self._bulb.setCustomPattern(
            colors,
            speed_pct,
            transition,
        )

    def RGBWW_brightness(
        self,
        rgbww_data: tuple[int, int, int, int] | tuple[int, int, int, int, int],
        brightness_255: int | None = None,
    ) -> tuple[tuple[int, int, int, int] | tuple[int, int, int, int, int], int]:
        """Convert RGBWW to brightness."""
        ww_brightness_255 = None
        cw_brightness_255 = None
        color_brightness_255 = None
        current_brightness_255 = None
        change_brightness_pct = None
        modified_rgbww = [0, 0, 0, 0, 0]

        ww_brightness_255 = rgbww_data[3]

        hsv_data = [*color_util.color_RGB_to_hsv(*rgbww_data[0:3])]
        color_brightness_255 = round(hsv_data[2] * 2.55)

        if len(rgbww_data) == 5:
            cw_brightness_255 = rgbww_data[-1]
            current_brightness_255 = round(
                (ww_brightness_255 + color_brightness_255 + cw_brightness_255) / 3
            )
        else:
            cw_brightness_255 = 0
            current_brightness_255 = round(
                (ww_brightness_255 + color_brightness_255) / 2
            )

        if not brightness_255 or brightness_255 == current_brightness_255:
            return (rgbww_data, current_brightness_255)

        if brightness_255 < current_brightness_255:
            change_brightness_pct = (
                current_brightness_255 - brightness_255
            ) / current_brightness_255
            ww_brightness_255 = round(ww_brightness_255 * (1 - change_brightness_pct))
            color_brightness_255 = round(
                color_brightness_255 * (1 - change_brightness_pct)
            )
            cw_brightness_255 = round(cw_brightness_255 * (1 - change_brightness_pct))

        else:
            change_brightness_pct = (brightness_255 - current_brightness_255) / (
                255 - current_brightness_255
            )
            ww_brightness_255 = round(
                (255 - ww_brightness_255) * (change_brightness_pct) + ww_brightness_255
            )
            color_brightness_255 = round(
                (255 - color_brightness_255) * (change_brightness_pct)
                + color_brightness_255
            )
            cw_brightness_255 = round(
                (255 - cw_brightness_255) * (change_brightness_pct) + cw_brightness_255
            )

        hsv_data[2] = color_brightness_255 / 2.55
        r, g, b = color_util.color_hsv_to_RGB(hsv_data[0], hsv_data[1], hsv_data[2])
        modified_rgbww[0] = r
        modified_rgbww[1] = g
        modified_rgbww[2] = b
        modified_rgbww[3] = ww_brightness_255
        if len(rgbww_data) == 5:
            modified_rgbww[4] = cw_brightness_255
        return (
            cast(tuple[int, int, int, int, int], tuple(modified_rgbww)),
            brightness_255,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the specified or all lights off."""
        await self.hass.async_add_executor_job(self._bulb.turnOff)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        if self._mode and self._mode != MODE_AUTO:
            return

        if self._bulb.mode == "ww":
            self._mode = MODE_WHITE
        elif self._bulb.rgbwcapable:
            self._mode = MODE_RGBW
        else:
            self._mode = MODE_RGB
        _LOGGER.debug(
            "Detected mode for %s (%s) with raw_state=%s rgbwcapable=%s is %s",
            self.name,
            self.unique_id,
            self._bulb.raw_state,
            self._bulb.rgbwcapable,
            self._mode,
        )
