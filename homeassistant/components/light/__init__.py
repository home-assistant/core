"""Provides functionality to interact with lights."""
from __future__ import annotations

import csv
import dataclasses
from datetime import timedelta
import logging
import os
from typing import cast, final

import voluptuous as vol

from homeassistant.const import (
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
    make_entity_service_schema,
)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.loader import bind_hass
import homeassistant.util.color as color_util

# mypy: allow-untyped-defs, no-check-untyped-defs

DOMAIN = "light"
SCAN_INTERVAL = timedelta(seconds=30)
DATA_PROFILES = "light_profiles"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

# Bitfield of features supported by the light entity
SUPPORT_BRIGHTNESS = 1  # Deprecated, replaced by color modes
SUPPORT_COLOR_TEMP = 2  # Deprecated, replaced by color modes
SUPPORT_EFFECT = 4
SUPPORT_FLASH = 8
SUPPORT_COLOR = 16  # Deprecated, replaced by color modes
SUPPORT_TRANSITION = 32
SUPPORT_WHITE_VALUE = 128  # Deprecated, replaced by color modes

# Color mode of the light
ATTR_COLOR_MODE = "color_mode"
# List of color modes supported by the light
ATTR_SUPPORTED_COLOR_MODES = "supported_color_modes"
# Possible color modes
COLOR_MODE_UNKNOWN = "unknown"  # Ambiguous color mode
COLOR_MODE_ONOFF = "onoff"  # Must be the only supported mode
COLOR_MODE_BRIGHTNESS = "brightness"  # Must be the only supported mode
COLOR_MODE_COLOR_TEMP = "color_temp"
COLOR_MODE_HS = "hs"
COLOR_MODE_XY = "xy"
COLOR_MODE_RGB = "rgb"
COLOR_MODE_RGBW = "rgbw"
COLOR_MODE_RGBWW = "rgbww"

VALID_COLOR_MODES = {
    COLOR_MODE_ONOFF,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    COLOR_MODE_XY,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    COLOR_MODE_RGBWW,
}
COLOR_MODES_BRIGHTNESS = VALID_COLOR_MODES - {COLOR_MODE_ONOFF}
COLOR_MODES_COLOR = {COLOR_MODE_HS, COLOR_MODE_RGB, COLOR_MODE_XY}


def valid_supported_color_modes(color_modes):
    """Validate the given color modes."""
    color_modes = set(color_modes)
    if (
        not color_modes
        or COLOR_MODE_UNKNOWN in color_modes
        or (COLOR_MODE_BRIGHTNESS in color_modes and len(color_modes) > 1)
        or (COLOR_MODE_ONOFF in color_modes and len(color_modes) > 1)
    ):
        raise vol.Error(f"Invalid supported_color_modes {sorted(color_modes)}")
    return color_modes


def brightness_supported(color_modes):
    """Test if brightness is supported."""
    if not color_modes:
        return False
    return any(mode in COLOR_MODES_BRIGHTNESS for mode in color_modes)


def color_supported(color_modes):
    """Test if color is supported."""
    if not color_modes:
        return False
    return any(mode in COLOR_MODES_COLOR for mode in color_modes)


def color_temp_supported(color_modes):
    """Test if color temperature is supported."""
    if not color_modes:
        return False
    return COLOR_MODE_COLOR_TEMP in color_modes


# Float that represents transition time in seconds to make change.
ATTR_TRANSITION = "transition"

# Lists holding color values
ATTR_RGB_COLOR = "rgb_color"
ATTR_RGBW_COLOR = "rgbw_color"
ATTR_RGBWW_COLOR = "rgbww_color"
ATTR_XY_COLOR = "xy_color"
ATTR_HS_COLOR = "hs_color"
ATTR_COLOR_TEMP = "color_temp"
ATTR_KELVIN = "kelvin"
ATTR_MIN_MIREDS = "min_mireds"
ATTR_MAX_MIREDS = "max_mireds"
ATTR_COLOR_NAME = "color_name"
ATTR_WHITE_VALUE = "white_value"

# Brightness of the light, 0..255 or percentage
ATTR_BRIGHTNESS = "brightness"
ATTR_BRIGHTNESS_PCT = "brightness_pct"
ATTR_BRIGHTNESS_STEP = "brightness_step"
ATTR_BRIGHTNESS_STEP_PCT = "brightness_step_pct"

# String representing a profile (built-in ones or external defined).
ATTR_PROFILE = "profile"

# If the light should flash, can be FLASH_SHORT or FLASH_LONG.
ATTR_FLASH = "flash"
FLASH_SHORT = "short"
FLASH_LONG = "long"

# List of possible effects
ATTR_EFFECT_LIST = "effect_list"

# Apply an effect to the light, can be EFFECT_COLORLOOP.
ATTR_EFFECT = "effect"
EFFECT_COLORLOOP = "colorloop"
EFFECT_RANDOM = "random"
EFFECT_WHITE = "white"

COLOR_GROUP = "Color descriptors"

LIGHT_PROFILES_FILE = "light_profiles.csv"

# Service call validation schemas
VALID_TRANSITION = vol.All(vol.Coerce(float), vol.Clamp(min=0, max=6553))
VALID_BRIGHTNESS = vol.All(vol.Coerce(int), vol.Clamp(min=0, max=255))
VALID_BRIGHTNESS_PCT = vol.All(vol.Coerce(float), vol.Range(min=0, max=100))
VALID_BRIGHTNESS_STEP = vol.All(vol.Coerce(int), vol.Clamp(min=-255, max=255))
VALID_BRIGHTNESS_STEP_PCT = vol.All(vol.Coerce(float), vol.Clamp(min=-100, max=100))
VALID_FLASH = vol.In([FLASH_SHORT, FLASH_LONG])

LIGHT_TURN_ON_SCHEMA = {
    vol.Exclusive(ATTR_PROFILE, COLOR_GROUP): cv.string,
    ATTR_TRANSITION: VALID_TRANSITION,
    vol.Exclusive(ATTR_BRIGHTNESS, ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
    vol.Exclusive(ATTR_BRIGHTNESS_PCT, ATTR_BRIGHTNESS): VALID_BRIGHTNESS_PCT,
    vol.Exclusive(ATTR_BRIGHTNESS_STEP, ATTR_BRIGHTNESS): VALID_BRIGHTNESS_STEP,
    vol.Exclusive(ATTR_BRIGHTNESS_STEP_PCT, ATTR_BRIGHTNESS): VALID_BRIGHTNESS_STEP_PCT,
    vol.Exclusive(ATTR_COLOR_NAME, COLOR_GROUP): cv.string,
    vol.Exclusive(ATTR_RGB_COLOR, COLOR_GROUP): vol.All(
        vol.ExactSequence((cv.byte,) * 3), vol.Coerce(tuple)
    ),
    vol.Exclusive(ATTR_RGBW_COLOR, COLOR_GROUP): vol.All(
        vol.ExactSequence((cv.byte,) * 4), vol.Coerce(tuple)
    ),
    vol.Exclusive(ATTR_RGBWW_COLOR, COLOR_GROUP): vol.All(
        vol.ExactSequence((cv.byte,) * 5), vol.Coerce(tuple)
    ),
    vol.Exclusive(ATTR_XY_COLOR, COLOR_GROUP): vol.All(
        vol.ExactSequence((cv.small_float, cv.small_float)), vol.Coerce(tuple)
    ),
    vol.Exclusive(ATTR_HS_COLOR, COLOR_GROUP): vol.All(
        vol.ExactSequence(
            (
                vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
                vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            )
        ),
        vol.Coerce(tuple),
    ),
    vol.Exclusive(ATTR_COLOR_TEMP, COLOR_GROUP): vol.All(
        vol.Coerce(int), vol.Range(min=1)
    ),
    vol.Exclusive(ATTR_KELVIN, COLOR_GROUP): cv.positive_int,
    ATTR_WHITE_VALUE: vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
    ATTR_FLASH: VALID_FLASH,
    ATTR_EFFECT: cv.string,
}

LIGHT_TURN_OFF_SCHEMA = {ATTR_TRANSITION: VALID_TRANSITION, ATTR_FLASH: VALID_FLASH}


_LOGGER = logging.getLogger(__name__)


@bind_hass
def is_on(hass, entity_id):
    """Return if the lights are on based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_ON)


def preprocess_turn_on_alternatives(hass, params):
    """Process extra data for turn light on request.

    Async friendly.
    """
    # Bail out, we process this later.
    if ATTR_BRIGHTNESS_STEP in params or ATTR_BRIGHTNESS_STEP_PCT in params:
        return

    if ATTR_PROFILE in params:
        hass.data[DATA_PROFILES].apply_profile(params.pop(ATTR_PROFILE), params)

    color_name = params.pop(ATTR_COLOR_NAME, None)
    if color_name is not None:
        try:
            params[ATTR_RGB_COLOR] = color_util.color_name_to_rgb(color_name)
        except ValueError:
            _LOGGER.warning("Got unknown color %s, falling back to white", color_name)
            params[ATTR_RGB_COLOR] = (255, 255, 255)

    kelvin = params.pop(ATTR_KELVIN, None)
    if kelvin is not None:
        mired = color_util.color_temperature_kelvin_to_mired(kelvin)
        params[ATTR_COLOR_TEMP] = int(mired)

    brightness_pct = params.pop(ATTR_BRIGHTNESS_PCT, None)
    if brightness_pct is not None:
        params[ATTR_BRIGHTNESS] = round(255 * brightness_pct / 100)


def filter_turn_off_params(params):
    """Filter out params not used in turn off."""
    return {k: v for k, v in params.items() if k in (ATTR_TRANSITION, ATTR_FLASH)}


async def async_setup(hass, config):
    """Expose light control via state machine and services."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    profiles = hass.data[DATA_PROFILES] = Profiles(hass)
    await profiles.async_initialize()

    def preprocess_data(data):
        """Preprocess the service data."""
        base = {
            entity_field: data.pop(entity_field)
            for entity_field in cv.ENTITY_SERVICE_FIELDS
            if entity_field in data
        }

        preprocess_turn_on_alternatives(hass, data)
        base["params"] = data
        return base

    async def async_handle_light_on_service(light, call):
        """Handle turning a light on.

        If brightness is set to 0, this service will turn the light off.
        """
        params = dict(call.data["params"])

        # Zero brightness: Light will be turned off
        if params.get(ATTR_BRIGHTNESS) == 0:
            await async_handle_light_off_service(light, call)
            return

        # Only process params once we processed brightness step
        if params and (
            ATTR_BRIGHTNESS_STEP in params or ATTR_BRIGHTNESS_STEP_PCT in params
        ):
            brightness = light.brightness if light.is_on else 0

            if ATTR_BRIGHTNESS_STEP in params:
                brightness += params.pop(ATTR_BRIGHTNESS_STEP)

            else:
                brightness += round(params.pop(ATTR_BRIGHTNESS_STEP_PCT) / 100 * 255)

            params[ATTR_BRIGHTNESS] = max(0, min(255, brightness))

            preprocess_turn_on_alternatives(hass, params)

        if not params or not light.is_on:
            profiles.apply_default(light.entity_id, params)

        if params and ATTR_TRANSITION not in params:
            profiles.apply_default_transition(light.entity_id, params)

        supported_color_modes = light.supported_color_modes
        # Backwards compatibility: if an RGBWW color is specified, convert to RGB + W
        # for legacy lights
        if ATTR_RGBW_COLOR in params:
            legacy_supported_color_modes = (
                light._light_internal_supported_color_modes  # pylint: disable=protected-access
            )
            if (
                COLOR_MODE_RGBW in legacy_supported_color_modes
                and not supported_color_modes
            ):
                rgbw_color = params.pop(ATTR_RGBW_COLOR)
                params[ATTR_RGB_COLOR] = rgbw_color[0:3]
                params[ATTR_WHITE_VALUE] = rgbw_color[3]

        # If a color is specified, convert to the color space supported by the light
        # Backwards compatibility: Fall back to hs color if light.supported_color_modes
        # is not implemented
        if not supported_color_modes:
            if (rgb_color := params.pop(ATTR_RGB_COLOR, None)) is not None:
                params[ATTR_HS_COLOR] = color_util.color_RGB_to_hs(*rgb_color)
            elif (xy_color := params.pop(ATTR_XY_COLOR, None)) is not None:
                params[ATTR_HS_COLOR] = color_util.color_xy_to_hs(*xy_color)
        elif ATTR_HS_COLOR in params and COLOR_MODE_HS not in supported_color_modes:
            hs_color = params.pop(ATTR_HS_COLOR)
            if COLOR_MODE_RGB in supported_color_modes:
                params[ATTR_RGB_COLOR] = color_util.color_hs_to_RGB(*hs_color)
            elif COLOR_MODE_XY in supported_color_modes:
                params[ATTR_XY_COLOR] = color_util.color_hs_to_xy(*hs_color)
        elif ATTR_RGB_COLOR in params and COLOR_MODE_RGB not in supported_color_modes:
            rgb_color = params.pop(ATTR_RGB_COLOR)
            if COLOR_MODE_HS in supported_color_modes:
                params[ATTR_HS_COLOR] = color_util.color_RGB_to_hs(*rgb_color)
            elif COLOR_MODE_XY in supported_color_modes:
                params[ATTR_XY_COLOR] = color_util.color_RGB_to_xy(*rgb_color)
        elif ATTR_XY_COLOR in params and COLOR_MODE_XY not in supported_color_modes:
            xy_color = params.pop(ATTR_XY_COLOR)
            if COLOR_MODE_HS in supported_color_modes:
                params[ATTR_HS_COLOR] = color_util.color_xy_to_hs(*xy_color)
            elif COLOR_MODE_RGB in supported_color_modes:
                params[ATTR_RGB_COLOR] = color_util.color_xy_to_RGB(*xy_color)

        # Remove deprecated white value if the light supports color mode
        if supported_color_modes:
            params.pop(ATTR_WHITE_VALUE, None)

        await light.async_turn_on(**params)

    async def async_handle_light_off_service(light, call):
        """Handle turning off a light."""
        params = dict(call.data["params"])

        if ATTR_TRANSITION not in params:
            profiles.apply_default_transition(light.entity_id, params)

        await light.async_turn_off(**filter_turn_off_params(params))

    async def async_handle_toggle_service(light, call):
        """Handle toggling a light."""
        if light.is_on:
            await async_handle_light_off_service(light, call)
        else:
            await async_handle_light_on_service(light, call)

    # Listen for light on and light off service calls.

    component.async_register_entity_service(
        SERVICE_TURN_ON,
        vol.All(cv.make_entity_service_schema(LIGHT_TURN_ON_SCHEMA), preprocess_data),
        async_handle_light_on_service,
    )

    component.async_register_entity_service(
        SERVICE_TURN_OFF,
        vol.All(cv.make_entity_service_schema(LIGHT_TURN_OFF_SCHEMA), preprocess_data),
        async_handle_light_off_service,
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE,
        vol.All(cv.make_entity_service_schema(LIGHT_TURN_ON_SCHEMA), preprocess_data),
        async_handle_toggle_service,
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


def _coerce_none(value: str) -> None:
    """Coerce an empty string as None."""

    if not isinstance(value, str):
        raise vol.Invalid("Expected a string")

    if value:
        raise vol.Invalid("Not an empty string")


@dataclasses.dataclass
class Profile:
    """Representation of a profile."""

    name: str
    color_x: float | None = dataclasses.field(repr=False)
    color_y: float | None = dataclasses.field(repr=False)
    brightness: int | None
    transition: int | None = None
    hs_color: tuple[float, float] | None = dataclasses.field(init=False)

    SCHEMA = vol.Schema(  # pylint: disable=invalid-name
        vol.Any(
            vol.ExactSequence(
                (
                    str,
                    vol.Any(cv.small_float, _coerce_none),
                    vol.Any(cv.small_float, _coerce_none),
                    vol.Any(cv.byte, _coerce_none),
                )
            ),
            vol.ExactSequence(
                (
                    str,
                    vol.Any(cv.small_float, _coerce_none),
                    vol.Any(cv.small_float, _coerce_none),
                    vol.Any(cv.byte, _coerce_none),
                    vol.Any(VALID_TRANSITION, _coerce_none),
                )
            ),
        )
    )

    def __post_init__(self) -> None:
        """Convert xy to hs color."""
        if None in (self.color_x, self.color_y):
            self.hs_color = None
            return

        self.hs_color = color_util.color_xy_to_hs(
            cast(float, self.color_x), cast(float, self.color_y)
        )

    @classmethod
    def from_csv_row(cls, csv_row: list[str]) -> Profile:
        """Create profile from a CSV row tuple."""
        return cls(*cls.SCHEMA(csv_row))


class Profiles:
    """Representation of available color profiles."""

    def __init__(self, hass: HomeAssistant):
        """Initialize profiles."""
        self.hass = hass
        self.data: dict[str, Profile] = {}

    def _load_profile_data(self) -> dict[str, Profile]:
        """Load built-in profiles and custom profiles."""
        profile_paths = [
            os.path.join(os.path.dirname(__file__), LIGHT_PROFILES_FILE),
            self.hass.config.path(LIGHT_PROFILES_FILE),
        ]
        profiles = {}

        for profile_path in profile_paths:
            if not os.path.isfile(profile_path):
                continue
            with open(profile_path) as inp:
                reader = csv.reader(inp)

                # Skip the header
                next(reader, None)

                try:
                    for rec in reader:
                        profile = Profile.from_csv_row(rec)
                        profiles[profile.name] = profile

                except vol.MultipleInvalid as ex:
                    _LOGGER.error(
                        "Error parsing light profile row '%s' from %s: %s",
                        rec,
                        profile_path,
                        ex,
                    )
                    continue
        return profiles

    async def async_initialize(self) -> None:
        """Load and cache profiles."""
        self.data = await self.hass.async_add_executor_job(self._load_profile_data)

    @callback
    def apply_default(self, entity_id: str, params: dict) -> None:
        """Return the default profile for the given light."""
        for _entity_id in (entity_id, "group.all_lights"):
            name = f"{_entity_id}.default"
            if name in self.data:
                self.apply_profile(name, params)
                return

    @callback
    def apply_default_transition(self, entity_id: str, params: dict) -> None:
        """Return the transition attribute from the default profile for the given light."""
        for _entity_id in (entity_id, "group.all_lights"):
            name = f"{_entity_id}.default"
            if name in self.data and self.data[name].transition is not None:
                params.setdefault(ATTR_TRANSITION, self.data[name].transition)
                return

    @callback
    def apply_profile(self, name: str, params: dict) -> None:
        """Apply a profile."""
        profile = self.data.get(name)

        if profile is None:
            return

        if profile.hs_color is not None:
            params.setdefault(ATTR_HS_COLOR, profile.hs_color)
        if profile.brightness is not None:
            params.setdefault(ATTR_BRIGHTNESS, profile.brightness)
        if profile.transition is not None:
            params.setdefault(ATTR_TRANSITION, profile.transition)


class LightEntity(ToggleEntity):
    """Base class for light entities."""

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return None

    @property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        return None

    @property
    def _light_internal_color_mode(self) -> str:
        """Return the color mode of the light with backwards compatibility."""
        color_mode = self.color_mode

        if color_mode is None:
            # Backwards compatibility for color_mode added in 2021.4
            # Add warning in 2021.6, remove in 2021.10
            supported = self._light_internal_supported_color_modes

            if (
                COLOR_MODE_RGBW in supported
                and self.white_value is not None
                and self.hs_color is not None
            ):
                return COLOR_MODE_RGBW
            if COLOR_MODE_HS in supported and self.hs_color is not None:
                return COLOR_MODE_HS
            if COLOR_MODE_COLOR_TEMP in supported and self.color_temp is not None:
                return COLOR_MODE_COLOR_TEMP
            if COLOR_MODE_BRIGHTNESS in supported and self.brightness is not None:
                return COLOR_MODE_BRIGHTNESS
            if COLOR_MODE_ONOFF in supported:
                return COLOR_MODE_ONOFF
            return COLOR_MODE_UNKNOWN

        return color_mode

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        return None

    @property
    def xy_color(self) -> tuple[float, float] | None:
        """Return the xy color value [float, float]."""
        return None

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value [int, int, int]."""
        return None

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the rgbw color value [int, int, int, int]."""
        return None

    @property
    def _light_internal_rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the rgbw color value [int, int, int, int]."""
        rgbw_color = self.rgbw_color
        if (
            rgbw_color is None
            and self.hs_color is not None
            and self.white_value is not None
        ):
            # Backwards compatibility for rgbw_color added in 2021.4
            # Add warning in 2021.6, remove in 2021.10
            r, g, b = color_util.color_hs_to_RGB(  # pylint: disable=invalid-name
                *self.hs_color
            )
            w = self.white_value  # pylint: disable=invalid-name
            rgbw_color = (r, g, b, w)

        return rgbw_color

    @property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return the rgbww color value [int, int, int, int, int]."""
        return None

    @property
    def color_temp(self) -> int | None:
        """Return the CT color value in mireds."""
        return None

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        # Default to the Philips Hue value that HA has always assumed
        # https://developers.meethue.com/documentation/core-concepts
        return 153

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        # Default to the Philips Hue value that HA has always assumed
        # https://developers.meethue.com/documentation/core-concepts
        return 500

    @property
    def white_value(self) -> int | None:
        """Return the white value of this light between 0..255."""
        return None

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return None

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return None

    @property
    def capability_attributes(self):
        """Return capability attributes."""
        data = {}
        supported_features = self.supported_features

        if supported_features & SUPPORT_COLOR_TEMP:
            data[ATTR_MIN_MIREDS] = self.min_mireds
            data[ATTR_MAX_MIREDS] = self.max_mireds

        if supported_features & SUPPORT_EFFECT:
            data[ATTR_EFFECT_LIST] = self.effect_list

        data[ATTR_SUPPORTED_COLOR_MODES] = sorted(
            self._light_internal_supported_color_modes
        )

        return data

    def _light_internal_convert_color(self, color_mode: str) -> dict:
        data: dict[str, tuple] = {}
        if color_mode == COLOR_MODE_HS and self.hs_color:
            hs_color = self.hs_color
            data[ATTR_HS_COLOR] = (round(hs_color[0], 3), round(hs_color[1], 3))
            data[ATTR_RGB_COLOR] = color_util.color_hs_to_RGB(*hs_color)
            data[ATTR_XY_COLOR] = color_util.color_hs_to_xy(*hs_color)
        elif color_mode == COLOR_MODE_XY and self.xy_color:
            xy_color = self.xy_color
            data[ATTR_HS_COLOR] = color_util.color_xy_to_hs(*xy_color)
            data[ATTR_RGB_COLOR] = color_util.color_xy_to_RGB(*xy_color)
            data[ATTR_XY_COLOR] = (round(xy_color[0], 6), round(xy_color[1], 6))
        elif color_mode == COLOR_MODE_RGB and self.rgb_color:
            rgb_color = self.rgb_color
            data[ATTR_HS_COLOR] = color_util.color_RGB_to_hs(*rgb_color)
            data[ATTR_RGB_COLOR] = tuple(int(x) for x in rgb_color[0:3])
            data[ATTR_XY_COLOR] = color_util.color_RGB_to_xy(*rgb_color)
        return data

    @final
    @property
    def state_attributes(self):
        """Return state attributes."""
        if not self.is_on:
            return None

        data = {}
        supported_features = self.supported_features
        color_mode = self._light_internal_color_mode

        if color_mode not in self._light_internal_supported_color_modes:
            # Increase severity to warning in 2021.6, reject in 2021.10
            _LOGGER.debug(
                "%s: set to unsupported color_mode: %s, supported_color_modes: %s",
                self.entity_id,
                color_mode,
                self._light_internal_supported_color_modes,
            )

        data[ATTR_COLOR_MODE] = color_mode

        if color_mode in COLOR_MODES_BRIGHTNESS:
            data[ATTR_BRIGHTNESS] = self.brightness
        elif supported_features & SUPPORT_BRIGHTNESS:
            # Backwards compatibility for ambiguous / incomplete states
            # Add warning in 2021.6, remove in 2021.10
            data[ATTR_BRIGHTNESS] = self.brightness

        if color_mode == COLOR_MODE_COLOR_TEMP:
            data[ATTR_COLOR_TEMP] = self.color_temp

        if color_mode in COLOR_MODES_COLOR:
            data.update(self._light_internal_convert_color(color_mode))

        if color_mode == COLOR_MODE_RGBW:
            data[ATTR_RGBW_COLOR] = self._light_internal_rgbw_color

        if color_mode == COLOR_MODE_RGBWW:
            data[ATTR_RGBWW_COLOR] = self.rgbww_color

        if supported_features & SUPPORT_COLOR_TEMP and not self.supported_color_modes:
            # Backwards compatibility
            # Add warning in 2021.6, remove in 2021.10
            data[ATTR_COLOR_TEMP] = self.color_temp

        if supported_features & SUPPORT_WHITE_VALUE and not self.supported_color_modes:
            # Backwards compatibility
            # Add warning in 2021.6, remove in 2021.10
            data[ATTR_WHITE_VALUE] = self.white_value
            if self.hs_color is not None:
                data.update(self._light_internal_convert_color(COLOR_MODE_HS))

        if supported_features & SUPPORT_EFFECT:
            data[ATTR_EFFECT] = self.effect

        return {key: val for key, val in data.items() if val is not None}

    @property
    def _light_internal_supported_color_modes(self) -> set:
        """Calculate supported color modes with backwards compatibility."""
        supported_color_modes = self.supported_color_modes

        if supported_color_modes is None:
            # Backwards compatibility for supported_color_modes added in 2021.4
            # Add warning in 2021.6, remove in 2021.10
            supported_features = self.supported_features
            supported_color_modes = set()

            if supported_features & SUPPORT_COLOR_TEMP:
                supported_color_modes.add(COLOR_MODE_COLOR_TEMP)
            if supported_features & SUPPORT_COLOR:
                supported_color_modes.add(COLOR_MODE_HS)
            if supported_features & SUPPORT_WHITE_VALUE:
                supported_color_modes.add(COLOR_MODE_RGBW)
            if supported_features & SUPPORT_BRIGHTNESS and not supported_color_modes:
                supported_color_modes = {COLOR_MODE_BRIGHTNESS}

            if not supported_color_modes:
                supported_color_modes = {COLOR_MODE_ONOFF}

        return supported_color_modes

    @property
    def supported_color_modes(self) -> set | None:
        """Flag supported color modes."""
        return None

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return 0


class Light(LightEntity):
    """Representation of a light (for backwards compatibility)."""

    def __init_subclass__(cls, **kwargs):
        """Print deprecation warning."""
        super().__init_subclass__(**kwargs)
        _LOGGER.warning(
            "Light is deprecated, modify %s to extend LightEntity",
            cls.__name__,
        )


def legacy_supported_features(
    supported_features: int, supported_color_modes: list[str] | None
) -> int:
    """Calculate supported features with backwards compatibility."""
    # Backwards compatibility for supported_color_modes added in 2021.4
    if supported_color_modes is None:
        return supported_features
    if any(mode in supported_color_modes for mode in COLOR_MODES_COLOR):
        supported_features |= SUPPORT_COLOR
    if any(mode in supported_color_modes for mode in COLOR_MODES_BRIGHTNESS):
        supported_features |= SUPPORT_BRIGHTNESS
    if COLOR_MODE_COLOR_TEMP in supported_color_modes:
        supported_features |= SUPPORT_COLOR_TEMP

    return supported_features
