"""Support for FluxLED/MagicHome lights."""
from __future__ import annotations

import ast
import logging
import random
from typing import Any, Final, cast

from flux_led.const import ATTR_ID, ATTR_IPADDR
from flux_led.utils import (
    color_temp_to_white_levels,
    rgbcw_brightness,
    rgbcw_to_rgbwc,
    rgbw_brightness,
    rgbww_brightness,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_WHITE,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    COLOR_MODE_RGBWW,
    COLOR_MODE_WHITE,
    EFFECT_RANDOM,
    PLATFORM_SCHEMA,
    SUPPORT_EFFECT,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.const import (
    ATTR_MODE,
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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.color import (
    color_hs_to_RGB,
    color_RGB_to_hs,
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

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
    EFFECT_SUPPORT_MODES,
    FLUX_LED_DISCOVERY,
    MODE_AUTO,
    MODE_RGB,
    MODE_RGBW,
    MODE_WHITE,
    TRANSITION_GRADUAL,
    TRANSITION_JUMP,
    TRANSITION_STROBE,
)
from .entity import FluxOnOffEntity
from .util import _flux_color_mode_to_hass, _hass_color_modes

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLUX_LED: Final = SUPPORT_TRANSITION

# Constant color temp values for 2 flux_led special modes
# Warm-white and Cool-white modes
COLOR_TEMP_WARM_VS_COLD_WHITE_CUT_OFF: Final = 285

EFFECT_CUSTOM: Final = "custom"

SERVICE_CUSTOM_EFFECT: Final = "set_custom_effect"

CUSTOM_EFFECT_DICT: Final = {
    vol.Required(CONF_COLORS): vol.All(
        cv.ensure_list,
        vol.Length(min=1, max=16),
        [vol.All(vol.Coerce(tuple), vol.ExactSequence((cv.byte, cv.byte, cv.byte)))],
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
        device[ATTR_IPADDR]: device[ATTR_ID]
        for device in domain_data[FLUX_LED_DISCOVERY]
    }
    for host, device_config in config.get(CONF_DEVICES, {}).items():
        _LOGGER.warning(
            "Configuring flux_led via yaml is deprecated; the configuration for"
            " %s has been migrated to a config entry and can be safely removed",
            host,
        )
        custom_effects = device_config.get(CONF_CUSTOM_EFFECT, {})
        custom_effect_colors = None
        if CONF_COLORS in custom_effects:
            custom_effect_colors = str(custom_effects[CONF_COLORS])
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
                    CONF_CUSTOM_EFFECT_COLORS: custom_effect_colors,
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
        "async_set_custom_effect",
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
                list(custom_effect_colors),
                options.get(CONF_CUSTOM_EFFECT_SPEED_PCT, DEFAULT_EFFECT_SPEED),
                options.get(CONF_CUSTOM_EFFECT_TRANSITION, TRANSITION_GRADUAL),
            )
        ]
    )


class FluxLight(FluxOnOffEntity, CoordinatorEntity, LightEntity):
    """Representation of a Flux light."""

    def __init__(
        self,
        coordinator: FluxLedUpdateCoordinator,
        unique_id: str | None,
        name: str,
        custom_effect_colors: list[tuple[int, int, int]],
        custom_effect_speed_pct: int,
        custom_effect_transition: str,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator, unique_id, name)
        self._attr_supported_features = SUPPORT_FLUX_LED
        self._attr_min_mireds = (
            color_temperature_kelvin_to_mired(self._device.max_temp) + 1
        )  # for rounding
        self._attr_max_mireds = color_temperature_kelvin_to_mired(self._device.min_temp)
        self._attr_supported_color_modes = _hass_color_modes(self._device)
        if self._attr_supported_color_modes.intersection(EFFECT_SUPPORT_MODES):
            self._attr_supported_features |= SUPPORT_EFFECT
            self._attr_effect_list = [*self._device.effect_list, EFFECT_RANDOM]
            if custom_effect_colors:
                self._attr_effect_list.append(EFFECT_CUSTOM)
        self._custom_effect_colors = custom_effect_colors
        self._custom_effect_speed_pct = custom_effect_speed_pct
        self._custom_effect_transition = custom_effect_transition

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return cast(int, self._device.brightness)

    @property
    def color_temp(self) -> int:
        """Return the kelvin value of this light in mired."""
        return color_temperature_kelvin_to_mired(self._device.color_temp)

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        """Return the rgb color value."""
        # Note that we call color_RGB_to_hs and not color_RGB_to_hsv
        # to get the unscaled value since this is what the frontend wants
        # https://github.com/home-assistant/frontend/blob/e797c017614797bb11671496d6bd65863de22063/src/dialogs/more-info/controls/more-info-light.ts#L263
        rgb: tuple[int, int, int] = color_hs_to_RGB(*color_RGB_to_hs(*self._device.rgb))
        return rgb

    @property
    def rgbw_color(self) -> tuple[int, int, int, int]:
        """Return the rgbw color value."""
        rgbw: tuple[int, int, int, int] = self._device.rgbw
        return rgbw

    @property
    def rgbww_color(self) -> tuple[int, int, int, int, int]:
        """Return the rgbww aka rgbcw color value."""
        rgbcw: tuple[int, int, int, int, int] = self._device.rgbcw
        return rgbcw

    @property
    def rgbwc_color(self) -> tuple[int, int, int, int, int]:
        """Return the rgbwc color value."""
        rgbwc: tuple[int, int, int, int, int] = self._device.rgbww
        return rgbwc

    @property
    def color_mode(self) -> str:
        """Return the color mode of the light."""
        return _flux_color_mode_to_hass(
            self._device.color_mode, self._device.color_modes
        )

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        effect = self._device.effect
        if effect is None:
            return None
        return cast(str, effect)

    async def _async_turn_on(self, **kwargs: Any) -> None:
        """Turn the specified or all lights on."""
        if not self.is_on:
            await self._device.async_turn_on()
        if not kwargs:
            return
        if effect := kwargs.get(ATTR_EFFECT):
            await self._async_set_effect(effect)
            return
        await self._async_set_colors(**kwargs)

    async def _async_set_effect(self, effect: str) -> None:
        """Set an effect."""
        # Random color effect
        if effect == EFFECT_RANDOM:
            await self._device.async_set_levels(
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255),
            )
            return
        # Custom effect
        if effect == EFFECT_CUSTOM:
            if self._custom_effect_colors:
                await self._device.async_set_custom_pattern(
                    self._custom_effect_colors,
                    self._custom_effect_speed_pct,
                    self._custom_effect_transition,
                )
            return
        await self._device.async_set_effect(
            effect, self._device.speed or DEFAULT_EFFECT_SPEED
        )

    async def _async_set_colors(self, **kwargs: Any) -> None:
        """Set color (can be done before turning on)."""
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is None:
            brightness = self.brightness
        if not brightness:
            # If the brightness was previously 0, the light
            # will not turn on unless brightness is at least 1
            # If the device was on and brightness was not
            # set, it means it was masked by an effect
            brightness = 255 if self.is_on else 1

        # Handle switch to CCT Color Mode
        if ATTR_COLOR_TEMP in kwargs:
            color_temp_mired = kwargs[ATTR_COLOR_TEMP]
            color_temp_kelvin = color_temperature_mired_to_kelvin(color_temp_mired)
            if self.color_mode != COLOR_MODE_RGBWW:
                await self._device.async_set_white_temp(color_temp_kelvin, brightness)
                return

            # When switching to color temp from RGBWW mode,
            # we do not want the overall brightness, we only
            # want the brightness of the white channels
            brightness = kwargs.get(
                ATTR_BRIGHTNESS, self._device.getWhiteTemperature()[1]
            )
            cold, warm = color_temp_to_white_levels(color_temp_kelvin, brightness)
            await self._device.async_set_levels(r=0, b=0, g=0, w=warm, w2=cold)
            return
        # Handle switch to RGB Color Mode
        if ATTR_RGB_COLOR in kwargs:
            await self._device.async_set_levels(
                *kwargs[ATTR_RGB_COLOR], brightness=brightness
            )
            return
        # Handle switch to RGBW Color Mode
        if ATTR_RGBW_COLOR in kwargs:
            if ATTR_BRIGHTNESS in kwargs:
                rgbw = rgbw_brightness(kwargs[ATTR_RGBW_COLOR], brightness)
            else:
                rgbw = kwargs[ATTR_RGBW_COLOR]
            await self._device.async_set_levels(*rgbw)
            return
        # Handle switch to RGBWW Color Mode
        if ATTR_RGBWW_COLOR in kwargs:
            if ATTR_BRIGHTNESS in kwargs:
                rgbcw = rgbcw_brightness(kwargs[ATTR_RGBWW_COLOR], brightness)
            else:
                rgbcw = kwargs[ATTR_RGBWW_COLOR]
            await self._device.async_set_levels(*rgbcw_to_rgbwc(rgbcw))
            return
        if ATTR_WHITE in kwargs:
            await self._device.async_set_levels(w=kwargs[ATTR_WHITE])
            return

        # Handle brightness adjustment in CCT Color Mode
        if self.color_mode == COLOR_MODE_COLOR_TEMP:
            await self._device.async_set_white_temp(self._device.color_temp, brightness)
            return
        # Handle brightness adjustment in RGB Color Mode
        if self.color_mode == COLOR_MODE_RGB:
            await self._device.async_set_levels(*self.rgb_color, brightness=brightness)
            return
        # Handle brightness adjustment in RGBW Color Mode
        if self.color_mode == COLOR_MODE_RGBW:
            await self._device.async_set_levels(
                *rgbw_brightness(self.rgbw_color, brightness)
            )
            return
        # Handle brightness adjustment in RGBWW Color Mode
        if self.color_mode == COLOR_MODE_RGBWW:
            rgbwc = self.rgbwc_color
            await self._device.async_set_levels(*rgbww_brightness(rgbwc, brightness))
            return
        # Handle Brightness Only Color Mode
        if self.color_mode in {COLOR_MODE_WHITE, COLOR_MODE_BRIGHTNESS}:
            await self._device.async_set_levels(w=brightness)
            return

    async def async_set_custom_effect(
        self, colors: list[tuple[int, int, int]], speed_pct: int, transition: str
    ) -> None:
        """Set a custom effect on the bulb."""
        await self._device.async_set_custom_pattern(
            colors,
            speed_pct,
            transition,
        )
