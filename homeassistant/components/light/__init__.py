"""Provides functionality to interact with lights."""
import csv
from datetime import timedelta
import logging
import os
from typing import Dict, Optional, Tuple

import voluptuous as vol

from homeassistant.const import (
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
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

ENTITY_ID_FORMAT = DOMAIN + ".{}"

# Bitfield of features supported by the light entity
SUPPORT_BRIGHTNESS = 1
SUPPORT_COLOR_TEMP = 2
SUPPORT_EFFECT = 4
SUPPORT_FLASH = 8
SUPPORT_COLOR = 16
SUPPORT_TRANSITION = 32
SUPPORT_WHITE_VALUE = 128

# Float that represents transition time in seconds to make change.
ATTR_TRANSITION = "transition"

# Lists holding color values
ATTR_RGB_COLOR = "rgb_color"
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
        vol.ExactSequence((cv.byte, cv.byte, cv.byte)), vol.Coerce(tuple)
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
    vol.Exclusive(ATTR_KELVIN, COLOR_GROUP): vol.All(vol.Coerce(int), vol.Range(min=0)),
    ATTR_WHITE_VALUE: vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
    ATTR_FLASH: VALID_FLASH,
    ATTR_EFFECT: cv.string,
}


PROFILE_SCHEMA = vol.Schema(
    vol.ExactSequence((str, cv.small_float, cv.small_float, cv.byte))
)

_LOGGER = logging.getLogger(__name__)


@bind_hass
def is_on(hass, entity_id):
    """Return if the lights are on based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_ON)


def preprocess_turn_on_alternatives(params):
    """Process extra data for turn light on request."""
    profile = Profiles.get(params.pop(ATTR_PROFILE, None))
    if profile is not None:
        params.setdefault(ATTR_XY_COLOR, profile[:2])
        params.setdefault(ATTR_BRIGHTNESS, profile[2])

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

    xy_color = params.pop(ATTR_XY_COLOR, None)
    if xy_color is not None:
        params[ATTR_HS_COLOR] = color_util.color_xy_to_hs(*xy_color)

    rgb_color = params.pop(ATTR_RGB_COLOR, None)
    if rgb_color is not None:
        params[ATTR_HS_COLOR] = color_util.color_RGB_to_hs(*rgb_color)


def preprocess_turn_off(params):
    """Process data for turning light off if brightness is 0."""
    if ATTR_BRIGHTNESS in params and params[ATTR_BRIGHTNESS] == 0:
        # Zero brightness: Light will be turned off
        params = {k: v for k, v in params.items() if k in (ATTR_TRANSITION, ATTR_FLASH)}
        return (True, params)  # Light should be turned off

    return (False, None)  # Light should be turned on


async def async_setup(hass, config):
    """Expose light control via state machine and services."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    # load profiles from files
    profiles_valid = await Profiles.load_profiles(hass)
    if not profiles_valid:
        return False

    def preprocess_data(data):
        """Preprocess the service data."""
        base = {
            entity_field: data.pop(entity_field)
            for entity_field in cv.ENTITY_SERVICE_FIELDS
            if entity_field in data
        }

        preprocess_turn_on_alternatives(data)
        turn_lights_off, off_params = preprocess_turn_off(data)

        base["params"] = data
        base["turn_lights_off"] = turn_lights_off
        base["off_params"] = off_params

        return base

    async def async_handle_light_on_service(light, call):
        """Handle turning a light on.

        If brightness is set to 0, this service will turn the light off.
        """
        params = call.data["params"]
        turn_light_off = call.data["turn_lights_off"]
        off_params = call.data["off_params"]

        if not params:
            default_profile = Profiles.get_default(light.entity_id)

            if default_profile is not None:
                params = {ATTR_PROFILE: default_profile}
                preprocess_turn_on_alternatives(params)
                turn_light_off, off_params = preprocess_turn_off(params)

        elif ATTR_BRIGHTNESS_STEP in params or ATTR_BRIGHTNESS_STEP_PCT in params:
            brightness = light.brightness if light.is_on else 0

            params = params.copy()

            if ATTR_BRIGHTNESS_STEP in params:
                brightness += params.pop(ATTR_BRIGHTNESS_STEP)

            else:
                brightness += round(params.pop(ATTR_BRIGHTNESS_STEP_PCT) / 100 * 255)

            params[ATTR_BRIGHTNESS] = max(0, min(255, brightness))
            turn_light_off, off_params = preprocess_turn_off(params)

        if turn_light_off:
            await light.async_turn_off(**off_params)
        else:
            await light.async_turn_on(**params)

    # Listen for light on and light off service calls.

    component.async_register_entity_service(
        SERVICE_TURN_ON,
        vol.All(cv.make_entity_service_schema(LIGHT_TURN_ON_SCHEMA), preprocess_data),
        async_handle_light_on_service,
    )

    component.async_register_entity_service(
        SERVICE_TURN_OFF,
        {ATTR_TRANSITION: VALID_TRANSITION, ATTR_FLASH: VALID_FLASH},
        "async_turn_off",
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE, LIGHT_TURN_ON_SCHEMA, "async_toggle"
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class Profiles:
    """Representation of available color profiles."""

    _all: Optional[Dict[str, Tuple[float, float, int]]] = None

    @classmethod
    async def load_profiles(cls, hass):
        """Load and cache profiles."""

        def load_profile_data(hass):
            """Load built-in profiles and custom profiles."""
            profile_paths = [
                os.path.join(os.path.dirname(__file__), LIGHT_PROFILES_FILE),
                hass.config.path(LIGHT_PROFILES_FILE),
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
                            profile, color_x, color_y, brightness = PROFILE_SCHEMA(rec)
                            profiles[profile] = (color_x, color_y, brightness)
                    except vol.MultipleInvalid as ex:
                        _LOGGER.error(
                            "Error parsing light profile from %s: %s", profile_path, ex
                        )
                        return None
            return profiles

        cls._all = await hass.async_add_job(load_profile_data, hass)
        return cls._all is not None

    @classmethod
    def get(cls, name):
        """Return a named profile."""
        return cls._all.get(name)

    @classmethod
    def get_default(cls, entity_id):
        """Return the default turn-on profile for the given light."""
        # pylint: disable=unsupported-membership-test
        name = f"{entity_id}.default"
        if name in cls._all:
            return name
        name = "group.all_lights.default"
        if name in cls._all:
            return name
        return None


class Light(ToggleEntity):
    """Representation of a light."""

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return None

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        return None

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        return None

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        # Default to the Philips Hue value that HA has always assumed
        # https://developers.meethue.com/documentation/core-concepts
        return 153

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        # Default to the Philips Hue value that HA has always assumed
        # https://developers.meethue.com/documentation/core-concepts
        return 500

    @property
    def white_value(self):
        """Return the white value of this light between 0..255."""
        return None

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return None

    @property
    def effect(self):
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

        return data

    @property
    def state_attributes(self):
        """Return state attributes."""
        if not self.is_on:
            return None

        data = {}
        supported_features = self.supported_features

        if supported_features & SUPPORT_BRIGHTNESS:
            data[ATTR_BRIGHTNESS] = self.brightness

        if supported_features & SUPPORT_COLOR_TEMP:
            data[ATTR_COLOR_TEMP] = self.color_temp

        if supported_features & SUPPORT_COLOR and self.hs_color:
            # pylint: disable=unsubscriptable-object,not-an-iterable
            hs_color = self.hs_color
            data[ATTR_HS_COLOR] = (round(hs_color[0], 3), round(hs_color[1], 3))
            data[ATTR_RGB_COLOR] = color_util.color_hs_to_RGB(*hs_color)
            data[ATTR_XY_COLOR] = color_util.color_hs_to_xy(*hs_color)

        if supported_features & SUPPORT_WHITE_VALUE:
            data[ATTR_WHITE_VALUE] = self.white_value

        if supported_features & SUPPORT_EFFECT:
            data[ATTR_EFFECT] = self.effect

        return {key: val for key, val in data.items() if val is not None}

    @property
    def supported_features(self):
        """Flag supported features."""
        return 0
