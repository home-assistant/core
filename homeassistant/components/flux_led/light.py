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
    ATTR_WHITE_VALUE,
    EFFECT_COLORLOOP,
    EFFECT_RANDOM,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_EFFECT,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODE,
    ATTR_MODEL,
    ATTR_NAME,
    CONF_DEVICES,
    CONF_HOST,
    CONF_MAC,
    CONF_MODE,
    CONF_NAME,
    CONF_PROTOCOL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
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
    MODE_RGB,
    MODE_RGBW,
    MODE_WHITE,
    TRANSITION_GRADUAL,
    TRANSITION_JUMP,
    TRANSITION_STROBE,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLUX_LED: Final = SUPPORT_BRIGHTNESS | SUPPORT_EFFECT | SUPPORT_COLOR


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
        self._name = name
        self._unique_id = unique_id
        self._ip_address = coordinator.host
        self._mode = mode
        self._custom_effect_colors = custom_effect_colors
        self._custom_effect_speed_pct = custom_effect_speed_pct
        self._custom_effect_transition = custom_effect_transition

    @property
    def unique_id(self) -> str | None:
        """Return the unique ID of the light."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return cast(bool, self._bulb.is_on)

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        if self._mode == MODE_WHITE:
            return self.white_value
        return cast(int, self._bulb.brightness)

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the color property."""
        return color_util.color_RGB_to_hs(*self._bulb.getRgb())

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        if self._mode == MODE_WHITE:
            return SUPPORT_BRIGHTNESS
        if self._mode in WHITE_MODES:
            return SUPPORT_FLUX_LED | SUPPORT_WHITE_VALUE | SUPPORT_COLOR_TEMP
        return SUPPORT_FLUX_LED

    @property
    def white_value(self) -> int:
        """Return the white value of this light between 0..255."""
        return cast(int, self._bulb.getRgbw()[3])

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
        return {
            "ip_address": self._ip_address,
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        assert self._unique_id is not None
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._unique_id)},
            ATTR_NAME: self._name,
            ATTR_MANUFACTURER: "FluxLED/Magic Home",
            ATTR_MODEL: "LED Lights",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the specified or all lights on."""
        await self.hass.async_add_executor_job(partial(self._turn_on, **kwargs))
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _turn_on(self, **kwargs: Any) -> None:
        """Turn the specified or all lights on."""
        if not self.is_on:
            self._bulb.turnOn()

        if hs_color := kwargs.get(ATTR_HS_COLOR):
            rgb: tuple[int, int, int] | None = color_util.color_hs_to_RGB(*hs_color)
        else:
            rgb = None

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        # handle special modes
        if (color_temp := kwargs.get(ATTR_COLOR_TEMP)) is not None:
            if brightness is None:
                brightness = self.brightness
            if color_temp > COLOR_TEMP_WARM_VS_COLD_WHITE_CUT_OFF:
                self._bulb.setRgbw(w=brightness)
            else:
                self._bulb.setRgbw(w2=brightness)
            return

        white = kwargs.get(ATTR_WHITE_VALUE)
        effect = kwargs.get(ATTR_EFFECT)
        # Show warning if effect set with rgb, brightness, or white level
        if effect and (brightness or white or rgb):
            _LOGGER.warning(
                "RGB, brightness and white level are ignored when"
                " an effect is specified for a flux bulb"
            )

        # Random color effect
        if effect == EFFECT_RANDOM:
            self._bulb.setRgb(
                random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
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
            self._bulb.setPresetPattern(EFFECT_MAP[effect], 50)
            return

        # Preserve current brightness on color/white level change
        if brightness is None:
            brightness = self.brightness

        # handle W only mode (use brightness instead of white value)
        if self._mode == MODE_WHITE:
            self._bulb.setRgbw(0, 0, 0, w=brightness)
            return

        if white is None and self._mode in WHITE_MODES:
            white = self.white_value

        # Preserve color on brightness/white level change
        if rgb is None:
            rgb = self._bulb.getRgb()

        # handle RGBW mode
        if self._mode == MODE_RGBW:
            self._bulb.setRgbw(*tuple(rgb), w=white, brightness=brightness)
            return

        # handle RGB mode
        self._bulb.setRgb(*tuple(rgb), brightness=brightness)

    def set_custom_effect(
        self, colors: list[tuple[int, int, int]], speed_pct: int, transition: str
    ) -> None:
        """Set a custom effect on the bulb."""
        self._bulb.setCustomPattern(
            colors,
            speed_pct,
            transition,
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
            self._name,
            self.unique_id,
            self._bulb.raw_state,
            self._bulb.rgbwcapable,
            self._mode,
        )
