"""Support for ADS light sources."""

from __future__ import annotations

from typing import Any

import pyads
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
    filter_supported_color_modes,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_ADS_VAR, DATA_ADS, STATE_KEY_STATE
from .entity import AdsEntity
from .hub import AdsHub

CONF_ADS_VAR_BRIGHTNESS = "adsvar_brightness"
CONF_MIN_BRIGHTNESS = "min_brightness"
CONF_MAX_BRIGHTNESS = "max_brightness"
CONF_ADS_VAR_COLOR_TEMP_KELVIN = "adsvar_color_temp_kelvin"
CONF_MIN_COLOR_TEMP_KELVIN = "min_color_temp_kelvin"
CONF_MAX_COLOR_TEMP_KELVIN = "max_color_temp_kelvin"
CONF_ADS_VAR_RED = "adsvar_red"
CONF_ADS_VAR_GREEN = "adsvar_green"
CONF_ADS_VAR_BLUE = "adsvar_blue"
CONF_ADS_VAR_WHITE = "adsvar_white"
CONF_ADS_VAR_HUE = "adsvar_hue"
CONF_ADS_VAR_SATURATION = "adsvar_saturation"
CONF_ADS_VAR_COLOR_MODE = "adsvar_color_mode"

STATE_KEY_BRIGHTNESS = "brightness"
STATE_KEY_COLOR_TEMP_KELVIN = "color_temp_kelvin"
STATE_KEY_RED = "red"
STATE_KEY_GREEN = "green"
STATE_KEY_BLUE = "blue"
STATE_KEY_WHITE = "white"
STATE_KEY_HUE = "hue"
STATE_KEY_SATURATION = "saturation"
STATE_KEY_COLOR_MODE = "color_mode"

DEFAULT_NAME = "ADS Light"
DEFAULT_MIN_BRIGHTNESS = 0
DEFAULT_MAX_BRIGHTNESS = 255


def _validate_brightness_range(config: ConfigType) -> ConfigType:
    """Ensure 0 <= min_brightness < max_brightness."""
    min_b = config.get(CONF_MIN_BRIGHTNESS, DEFAULT_MIN_BRIGHTNESS)
    max_b = config.get(CONF_MAX_BRIGHTNESS, DEFAULT_MAX_BRIGHTNESS)
    if min_b >= max_b:
        raise vol.Invalid("min_brightness must be less than max_brightness")
    return config


def _validate_channel_groups(config: ConfigType) -> ConfigType:
    """Require colour channels to be configured as complete groups.

    Partial definitions (e.g. only adsvar_hue without adsvar_saturation, or
    adsvar_red without adsvar_green/adsvar_blue) would silently subscribe to
    ADS variable updates without ever advertising the corresponding colour
    mode, which is hard to debug.
    """
    has_hue = CONF_ADS_VAR_HUE in config
    has_sat = CONF_ADS_VAR_SATURATION in config
    if has_hue != has_sat:
        raise vol.Invalid(
            f"{CONF_ADS_VAR_HUE} and {CONF_ADS_VAR_SATURATION} must be"
            " configured together"
        )

    rgb_vars = (CONF_ADS_VAR_RED, CONF_ADS_VAR_GREEN, CONF_ADS_VAR_BLUE)
    rgb_present = [v in config for v in rgb_vars]
    if any(rgb_present) and not all(rgb_present):
        raise vol.Invalid(
            f"{CONF_ADS_VAR_RED}, {CONF_ADS_VAR_GREEN}, and {CONF_ADS_VAR_BLUE}"
            " must all be configured together"
        )

    if CONF_ADS_VAR_WHITE in config and not all(rgb_present):
        raise vol.Invalid(
            f"{CONF_ADS_VAR_WHITE} requires {CONF_ADS_VAR_RED},"
            f" {CONF_ADS_VAR_GREEN}, and {CONF_ADS_VAR_BLUE} to also be"
            " configured"
        )

    return config


def _validate_brightness_required_for_color(config: ConfigType) -> ConfigType:
    """Require adsvar_brightness when color modes that need it are configured.

    COLOR_TEMP and HS do not encode brightness in their channel values, so a
    separate brightness variable is mandatory to avoid silently dropping
    brightness commands from Home Assistant.
    """
    has_brightness = CONF_ADS_VAR_BRIGHTNESS in config
    if not has_brightness and CONF_ADS_VAR_COLOR_TEMP_KELVIN in config:
        raise vol.Invalid(
            f"{CONF_ADS_VAR_BRIGHTNESS} is required when"
            f" {CONF_ADS_VAR_COLOR_TEMP_KELVIN} is configured"
        )
    if not has_brightness and CONF_ADS_VAR_HUE in config:
        raise vol.Invalid(
            f"{CONF_ADS_VAR_BRIGHTNESS} is required when"
            f" {CONF_ADS_VAR_HUE} and {CONF_ADS_VAR_SATURATION} are configured"
        )
    return config


PLATFORM_SCHEMA = vol.All(
    LIGHT_PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_ADS_VAR): cv.string,
            vol.Optional(CONF_ADS_VAR_BRIGHTNESS): cv.string,
            vol.Optional(CONF_MIN_BRIGHTNESS, default=DEFAULT_MIN_BRIGHTNESS): vol.All(
                vol.Coerce(int), vol.Range(min=0)
            ),
            vol.Optional(CONF_MAX_BRIGHTNESS, default=DEFAULT_MAX_BRIGHTNESS): vol.All(
                vol.Coerce(int), vol.Range(min=0)
            ),
            vol.Optional(CONF_ADS_VAR_COLOR_TEMP_KELVIN): cv.string,
            vol.Optional(CONF_MIN_COLOR_TEMP_KELVIN): cv.positive_int,
            vol.Optional(CONF_MAX_COLOR_TEMP_KELVIN): cv.positive_int,
            vol.Optional(CONF_ADS_VAR_RED): cv.string,
            vol.Optional(CONF_ADS_VAR_GREEN): cv.string,
            vol.Optional(CONF_ADS_VAR_BLUE): cv.string,
            vol.Optional(CONF_ADS_VAR_WHITE): cv.string,
            vol.Optional(CONF_ADS_VAR_HUE): cv.string,
            vol.Optional(CONF_ADS_VAR_SATURATION): cv.string,
            vol.Optional(CONF_ADS_VAR_COLOR_MODE): cv.string,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        }
    ),
    _validate_brightness_range,
    _validate_channel_groups,
    _validate_brightness_required_for_color,
)


def _scale_value(
    value: int, from_min: int, from_max: int, to_min: int, to_max: int
) -> int:
    """Scale a value linearly from one numeric range to another.

    Returns to_min when from_min equals from_max to avoid a division by zero.
    """
    if from_max == from_min:
        return to_min
    return round(
        to_min + (value - from_min) * (to_max - to_min) / (from_max - from_min)
    )


def _map_color_mode(raw: int) -> ColorMode:
    """Map a TwinCAT bitmask value to a single Home Assistant ColorMode.

    The PLC writes a bitmask where each bit represents one capability:
      Bit 0 (1)  – on/off only
      Bit 1 (2)  – brightness (dimmer)
      Bit 2 (4)  – color temperature
      Bit 3 (8)  – hue/saturation
      Bit 4 (16) – RGB
      Bit 5 (32) – white channel
    RGBW is indicated by bits 4 and 5 set simultaneously (value 48).
    When bit 5 is set without bit 4 (i.e. white without RGB), ColorMode.WHITE
    is avoided: if bit 2 (color temperature) is also set, WHITE is returned so
    the caller can choose; otherwise BRIGHTNESS is returned because Home
    Assistant requires at least one other mode alongside WHITE.
    """
    if (raw & 16) and (raw & 32):
        return ColorMode.RGBW
    if raw & 16:
        return ColorMode.RGB
    if raw & 8:
        return ColorMode.HS
    if raw & 32:
        # Bit 4 (RGB) and bit 3 (HS) are guaranteed 0 here (handled above).
        # Return BRIGHTNESS when only the white channel is active; ColorMode.WHITE
        # must not be the only supported mode per Home Assistant requirements.
        return ColorMode.BRIGHTNESS if not (raw & 4) else ColorMode.WHITE
    if raw & 4:
        return ColorMode.COLOR_TEMP
    if raw & 2:
        return ColorMode.BRIGHTNESS
    return ColorMode.ONOFF


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the light platform for ADS."""
    ads_hub = hass.data[DATA_ADS]

    ads_var_enable: str = config[CONF_ADS_VAR]
    ads_var_brightness: str | None = config.get(CONF_ADS_VAR_BRIGHTNESS)
    min_brightness: int = config[CONF_MIN_BRIGHTNESS]
    max_brightness: int = config[CONF_MAX_BRIGHTNESS]
    ads_var_color_temp_kelvin: str | None = config.get(CONF_ADS_VAR_COLOR_TEMP_KELVIN)
    min_color_temp_kelvin: int | None = config.get(CONF_MIN_COLOR_TEMP_KELVIN)
    max_color_temp_kelvin: int | None = config.get(CONF_MAX_COLOR_TEMP_KELVIN)
    ads_var_red: str | None = config.get(CONF_ADS_VAR_RED)
    ads_var_green: str | None = config.get(CONF_ADS_VAR_GREEN)
    ads_var_blue: str | None = config.get(CONF_ADS_VAR_BLUE)
    ads_var_white: str | None = config.get(CONF_ADS_VAR_WHITE)
    ads_var_hue: str | None = config.get(CONF_ADS_VAR_HUE)
    ads_var_saturation: str | None = config.get(CONF_ADS_VAR_SATURATION)
    ads_var_color_mode: str | None = config.get(CONF_ADS_VAR_COLOR_MODE)
    name: str = config[CONF_NAME]

    add_entities(
        [
            AdsLight(
                ads_hub,
                ads_var_enable,
                ads_var_brightness,
                min_brightness,
                max_brightness,
                ads_var_color_temp_kelvin,
                min_color_temp_kelvin,
                max_color_temp_kelvin,
                ads_var_red,
                ads_var_green,
                ads_var_blue,
                ads_var_white,
                ads_var_hue,
                ads_var_saturation,
                ads_var_color_mode,
                name,
            )
        ]
    )


class AdsLight(AdsEntity, LightEntity):
    """Representation of ADS light."""

    def __init__(
        self,
        ads_hub: AdsHub,
        ads_var_enable: str,
        ads_var_brightness: str | None,
        min_brightness: int,
        max_brightness: int,
        ads_var_color_temp_kelvin: str | None,
        min_color_temp_kelvin: int | None,
        max_color_temp_kelvin: int | None,
        ads_var_red: str | None,
        ads_var_green: str | None,
        ads_var_blue: str | None,
        ads_var_white: str | None,
        ads_var_hue: str | None,
        ads_var_saturation: str | None,
        ads_var_color_mode: str | None,
        name: str,
    ) -> None:
        """Initialize AdsLight entity."""
        super().__init__(ads_hub, name, ads_var_enable)
        self._state_dict[STATE_KEY_BRIGHTNESS] = None
        self._state_dict[STATE_KEY_COLOR_TEMP_KELVIN] = None
        self._state_dict[STATE_KEY_RED] = None
        self._state_dict[STATE_KEY_GREEN] = None
        self._state_dict[STATE_KEY_BLUE] = None
        self._state_dict[STATE_KEY_WHITE] = None
        self._state_dict[STATE_KEY_HUE] = None
        self._state_dict[STATE_KEY_SATURATION] = None
        self._state_dict[STATE_KEY_COLOR_MODE] = None

        self._ads_var_brightness = ads_var_brightness
        self._min_brightness = min_brightness
        self._max_brightness = max_brightness
        self._ads_var_color_temp_kelvin = ads_var_color_temp_kelvin
        self._ads_var_red = ads_var_red
        self._ads_var_green = ads_var_green
        self._ads_var_blue = ads_var_blue
        self._ads_var_white = ads_var_white
        self._ads_var_hue = ads_var_hue
        self._ads_var_saturation = ads_var_saturation
        self._ads_var_color_mode = ads_var_color_mode

        # Determine supported color modes from the configured channel variables
        color_modes = {ColorMode.ONOFF}
        if ads_var_brightness is not None:
            color_modes.add(ColorMode.BRIGHTNESS)
        if ads_var_color_temp_kelvin is not None:
            color_modes.add(ColorMode.COLOR_TEMP)
        if ads_var_hue is not None and ads_var_saturation is not None:
            color_modes.add(ColorMode.HS)
        if (
            ads_var_red is not None
            and ads_var_green is not None
            and ads_var_blue is not None
            and ads_var_white is not None
        ):
            color_modes.add(ColorMode.RGBW)
        elif (
            ads_var_red is not None
            and ads_var_green is not None
            and ads_var_blue is not None
        ):
            color_modes.add(ColorMode.RGB)

        self._attr_supported_color_modes = filter_supported_color_modes(color_modes)

        # Pick the richest supported mode as the static default (used as fallback).
        # The preferred order is deterministic so the result is stable across restarts.
        self._attr_color_mode = ColorMode.ONOFF
        for preferred in (
            ColorMode.RGBW,
            ColorMode.RGB,
            ColorMode.HS,
            ColorMode.COLOR_TEMP,
            ColorMode.BRIGHTNESS,
            ColorMode.ONOFF,
        ):
            if preferred in self._attr_supported_color_modes:
                self._attr_color_mode = preferred
                break

        # Color temperature range is only relevant when the CT channel is configured
        if ads_var_color_temp_kelvin is not None:
            self._attr_min_color_temp_kelvin = (
                min_color_temp_kelvin
                if min_color_temp_kelvin is not None
                else DEFAULT_MIN_KELVIN
            )
            self._attr_max_color_temp_kelvin = (
                max_color_temp_kelvin
                if max_color_temp_kelvin is not None
                else DEFAULT_MAX_KELVIN
            )

    def _scale_brightness_to_ads(self, hass_brightness: int) -> int:
        """Scale brightness from the Home Assistant range (0–255) to the ADS range."""
        return _scale_value(
            hass_brightness,
            0,
            255,
            self._min_brightness,
            self._max_brightness,
        )

    def _scale_brightness_from_ads(self, ads_brightness: int) -> int:
        """Scale brightness from the ADS range to the Home Assistant range (0–255)."""
        return _scale_value(
            ads_brightness,
            self._min_brightness,
            self._max_brightness,
            0,
            255,
        )

    async def async_added_to_hass(self) -> None:
        """Register device notifications; plc_datatype must match the PLC symbol."""
        await self.async_initialize_device(self._ads_var, pyads.PLCTYPE_BOOL)

        if self._ads_var_brightness is not None:
            await self.async_initialize_device(
                self._ads_var_brightness,
                pyads.PLCTYPE_UINT,
                STATE_KEY_BRIGHTNESS,
            )

        if self._ads_var_color_temp_kelvin is not None:
            await self.async_initialize_device(
                self._ads_var_color_temp_kelvin,
                pyads.PLCTYPE_UINT,
                STATE_KEY_COLOR_TEMP_KELVIN,
            )

        if self._ads_var_red is not None:
            await self.async_initialize_device(
                self._ads_var_red,
                pyads.PLCTYPE_USINT,
                STATE_KEY_RED,
            )

        if self._ads_var_green is not None:
            await self.async_initialize_device(
                self._ads_var_green,
                pyads.PLCTYPE_USINT,
                STATE_KEY_GREEN,
            )

        if self._ads_var_blue is not None:
            await self.async_initialize_device(
                self._ads_var_blue,
                pyads.PLCTYPE_USINT,
                STATE_KEY_BLUE,
            )

        if self._ads_var_white is not None:
            await self.async_initialize_device(
                self._ads_var_white,
                pyads.PLCTYPE_USINT,
                STATE_KEY_WHITE,
            )

        if self._ads_var_hue is not None:
            await self.async_initialize_device(
                self._ads_var_hue,
                pyads.PLCTYPE_UINT,
                STATE_KEY_HUE,
            )

        if self._ads_var_saturation is not None:
            await self.async_initialize_device(
                self._ads_var_saturation,
                pyads.PLCTYPE_UINT,
                STATE_KEY_SATURATION,
            )

        if self._ads_var_color_mode is not None:
            await self.async_initialize_device(
                self._ads_var_color_mode,
                pyads.PLCTYPE_UINT,
                STATE_KEY_COLOR_MODE,
            )

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light (0–255).

        When a dedicated brightness channel is configured it is used directly
        (scaled from the PLC range).  For RGB/RGBW lights without a separate
        brightness channel, brightness is derived from the maximum channel
        value so that Home Assistant can still report and scale it correctly.
        """
        ads_brightness = self._state_dict[STATE_KEY_BRIGHTNESS]
        if ads_brightness is not None:
            return max(
                0, min(255, self._scale_brightness_from_ads(int(ads_brightness)))
            )

        # Derive brightness from the color channels when no dedicated
        # brightness variable is configured (RGB/RGBW modes only).
        r = self._state_dict[STATE_KEY_RED]
        g = self._state_dict[STATE_KEY_GREEN]
        b = self._state_dict[STATE_KEY_BLUE]
        w = self._state_dict[STATE_KEY_WHITE]
        if r is not None and g is not None and b is not None:
            candidates = [int(r), int(g), int(b)]
            if w is not None:
                candidates.append(int(w))
            return max(candidates)

        return None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        return self._state_dict[STATE_KEY_COLOR_TEMP_KELVIN]

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float].

        Expects the PLC to use hue 0–360 degrees and saturation 0–100 percent.
        """
        hue = self._state_dict[STATE_KEY_HUE]
        saturation = self._state_dict[STATE_KEY_SATURATION]
        if hue is not None and saturation is not None:
            return (float(hue), float(saturation))
        return None

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color value [int, int, int]."""
        red = self._state_dict[STATE_KEY_RED]
        green = self._state_dict[STATE_KEY_GREEN]
        blue = self._state_dict[STATE_KEY_BLUE]
        if red is not None and green is not None and blue is not None:
            return (int(red), int(green), int(blue))
        return None

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the RGBW color value [int, int, int, int]."""
        red = self._state_dict[STATE_KEY_RED]
        green = self._state_dict[STATE_KEY_GREEN]
        blue = self._state_dict[STATE_KEY_BLUE]
        white = self._state_dict[STATE_KEY_WHITE]
        if (
            red is not None
            and green is not None
            and blue is not None
            and white is not None
        ):
            return (int(red), int(green), int(blue), int(white))
        return None

    @property
    def color_mode(self) -> ColorMode | None:
        """Return the active color mode of the light.

        When adsvar_color_mode is configured, the PLC reports the active mode
        as a bitmask (see _map_color_mode). Falls back to the statically
        determined default when the variable is absent or its value is not
        within the supported modes.
        """
        raw = self._state_dict.get(STATE_KEY_COLOR_MODE)
        if raw is not None:
            mapped = _map_color_mode(int(raw))
            if (
                self._attr_supported_color_modes
                and mapped in self._attr_supported_color_modes
            ):
                return mapped
        return self._attr_color_mode

    @property
    def is_on(self) -> bool:
        """Return True if the entity is on."""
        return self._state_dict[STATE_KEY_STATE]

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light on or set specific values."""
        to_write: list[tuple[str, Any]] = [(self._ads_var, True)]

        if self._ads_var_brightness is not None and ATTR_BRIGHTNESS in kwargs:
            to_write.append(
                (
                    self._ads_var_brightness,
                    self._scale_brightness_to_ads(kwargs[ATTR_BRIGHTNESS]),
                )
            )

        if (
            self._ads_var_color_temp_kelvin is not None
            and ATTR_COLOR_TEMP_KELVIN in kwargs
        ):
            to_write.append(
                (self._ads_var_color_temp_kelvin, kwargs[ATTR_COLOR_TEMP_KELVIN])
            )

        if (
            self._ads_var_hue is not None
            and self._ads_var_saturation is not None
            and ATTR_HS_COLOR in kwargs
        ):
            h, s = kwargs[ATTR_HS_COLOR]
            to_write.append((self._ads_var_hue, int(h)))
            to_write.append((self._ads_var_saturation, int(s)))

        if (
            self._ads_var_red is not None
            and self._ads_var_green is not None
            and self._ads_var_blue is not None
        ):
            # When no dedicated brightness channel is configured, bake the
            # requested brightness into the colour channel values.
            # HA sends colour normalised to full brightness (0-255 per channel)
            # and passes the actual brightness level separately, so multiplying
            # by brightness/255 produces the correct scaled output.
            brightness_factor = 1.0
            if self._ads_var_brightness is None and ATTR_BRIGHTNESS in kwargs:
                brightness_factor = kwargs[ATTR_BRIGHTNESS] / 255.0

            if self._ads_var_white is not None and ATTR_RGBW_COLOR in kwargs:
                r, g, b, w = kwargs[ATTR_RGBW_COLOR]
                to_write.extend(
                    [
                        (
                            self._ads_var_red,
                            min(255, round(int(r) * brightness_factor)),
                        ),
                        (
                            self._ads_var_green,
                            min(255, round(int(g) * brightness_factor)),
                        ),
                        (
                            self._ads_var_blue,
                            min(255, round(int(b) * brightness_factor)),
                        ),
                        (
                            self._ads_var_white,
                            min(255, round(int(w) * brightness_factor)),
                        ),
                    ]
                )
            elif ATTR_RGB_COLOR in kwargs:
                r, g, b = kwargs[ATTR_RGB_COLOR]
                to_write.extend(
                    [
                        (
                            self._ads_var_red,
                            min(255, round(int(r) * brightness_factor)),
                        ),
                        (
                            self._ads_var_green,
                            min(255, round(int(g) * brightness_factor)),
                        ),
                        (
                            self._ads_var_blue,
                            min(255, round(int(b) * brightness_factor)),
                        ),
                    ]
                )
            elif self._ads_var_brightness is None and ATTR_BRIGHTNESS in kwargs:
                # Brightness-only command without a colour: scale the current
                # channel values proportionally so hue/saturation is preserved.
                target = kwargs[ATTR_BRIGHTNESS]
                cur_r = int(self._state_dict[STATE_KEY_RED] or 0)
                cur_g = int(self._state_dict[STATE_KEY_GREEN] or 0)
                cur_b = int(self._state_dict[STATE_KEY_BLUE] or 0)
                current = max(cur_r, cur_g, cur_b)
                if current > 0:
                    scale = target / current
                    to_write.extend(
                        [
                            (self._ads_var_red, min(255, round(cur_r * scale))),
                            (self._ads_var_green, min(255, round(cur_g * scale))),
                            (self._ads_var_blue, min(255, round(cur_b * scale))),
                        ]
                    )
                    if self._ads_var_white is not None:
                        cur_w = int(self._state_dict[STATE_KEY_WHITE] or 0)
                        to_write.append(
                            (self._ads_var_white, min(255, round(cur_w * scale)))
                        )
                else:
                    # All channels are zero (e.g. light was off or state not yet
                    # received); initialise to neutral white at the requested level.
                    to_write.extend(
                        [
                            (self._ads_var_red, target),
                            (self._ads_var_green, target),
                            (self._ads_var_blue, target),
                        ]
                    )
                    if self._ads_var_white is not None:
                        to_write.append((self._ads_var_white, target))

        self._ads_hub.write_list_by_name(to_write)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self._ads_hub.write_by_name(self._ads_var, False, pyads.PLCTYPE_BOOL)
