"""Provides functionality to interact with lights."""

import csv
import dataclasses
import logging
import os
from typing import Any, Self, cast

import probatio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import color as color_util

from .const import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_BRIGHTNESS_STEP,
    ATTR_BRIGHTNESS_STEP_PCT,
    ATTR_COLOR_MODE,
    ATTR_COLOR_NAME,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_PROFILE,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    ATTR_WHITE,
    ATTR_XY_COLOR,
    COLOR_GROUP,
    COLOR_MODES_BRIGHTNESS,
    COLOR_MODES_COLOR,
    DATA_COMPONENT,
    DATA_PROFILES,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    DOMAIN,
    EFFECT_COLORLOOP,
    EFFECT_OFF,
    EFFECT_RANDOM,
    EFFECT_WHITE,
    FLASH_LONG,
    FLASH_SHORT,
    LIGHT_PROFILES_FILE,
    LIGHT_TURN_OFF_SCHEMA,
    LIGHT_TURN_ON_SCHEMA,
    SCAN_INTERVAL,
    VALID_BRIGHTNESS,
    VALID_BRIGHTNESS_PCT,
    VALID_BRIGHTNESS_STEP,
    VALID_BRIGHTNESS_STEP_PCT,
    VALID_COLOR_MODES,
    VALID_FLASH,
    VALID_TRANSITION,
    ColorMode,
    LightEntityCapabilityAttribute,
    LightEntityFeature,
    LightEntityStateAttribute,
    LightService,
    LightServiceArgument,
)
from .entity import LightEntity, LightEntityDescription
from .helper import (
    brightness_supported,
    color_supported,
    color_temp_supported,
    filter_supported_color_modes,
    filter_turn_off_params,
    filter_turn_on_params,
    get_supported_color_modes,
    preprocess_turn_on_alternatives,
    process_turn_off_params,
    process_turn_on_params,
    valid_supported_color_modes,
)
from .services import async_setup_services

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE


__all__ = [
    "ATTR_BRIGHTNESS",
    "ATTR_BRIGHTNESS_PCT",
    "ATTR_BRIGHTNESS_STEP",
    "ATTR_BRIGHTNESS_STEP_PCT",
    "ATTR_COLOR_MODE",
    "ATTR_COLOR_NAME",
    "ATTR_COLOR_TEMP_KELVIN",
    "ATTR_EFFECT",
    "ATTR_EFFECT_LIST",
    "ATTR_FLASH",
    "ATTR_HS_COLOR",
    "ATTR_MAX_COLOR_TEMP_KELVIN",
    "ATTR_MIN_COLOR_TEMP_KELVIN",
    "ATTR_PROFILE",
    "ATTR_RGBWW_COLOR",
    "ATTR_RGBW_COLOR",
    "ATTR_RGB_COLOR",
    "ATTR_SUPPORTED_COLOR_MODES",
    "ATTR_TRANSITION",
    "ATTR_WHITE",
    "ATTR_XY_COLOR",
    "COLOR_GROUP",
    "COLOR_MODES_BRIGHTNESS",
    "COLOR_MODES_COLOR",
    "DEFAULT_MAX_KELVIN",
    "DEFAULT_MIN_KELVIN",
    "DOMAIN",
    "EFFECT_COLORLOOP",
    "EFFECT_OFF",
    "EFFECT_RANDOM",
    "EFFECT_WHITE",
    "ENTITY_ID_FORMAT",
    "FLASH_LONG",
    "FLASH_SHORT",
    "LIGHT_TURN_OFF_SCHEMA",
    "LIGHT_TURN_ON_SCHEMA",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "SERVICE_TOGGLE",
    "SERVICE_TURN_OFF",
    "SERVICE_TURN_ON",
    "STATE_OFF",
    "STATE_ON",
    "VALID_BRIGHTNESS",
    "VALID_BRIGHTNESS_PCT",
    "VALID_BRIGHTNESS_STEP",
    "VALID_BRIGHTNESS_STEP_PCT",
    "VALID_COLOR_MODES",
    "VALID_FLASH",
    "VALID_TRANSITION",
    "ColorMode",
    "LightEntity",
    "LightEntityCapabilityAttribute",
    "LightEntityDescription",
    "LightEntityFeature",
    "LightEntityStateAttribute",
    "LightService",
    "LightServiceArgument",
    "Profiles",
    "brightness_supported",
    "color_supported",
    "color_temp_supported",
    "filter_supported_color_modes",
    "filter_turn_off_params",
    "filter_turn_on_params",
    "get_supported_color_modes",
    "is_on",
    "preprocess_turn_on_alternatives",
    "process_turn_off_params",
    "process_turn_on_params",
    "valid_supported_color_modes",
]

# mypy: disallow-any-generics


_LOGGER = logging.getLogger(__name__)


def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Return if the lights are on based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Expose light control via state machine and services."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[LightEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    profiles = hass.data[DATA_PROFILES] = Profiles(hass)
    # Profiles are loaded in a separate task to avoid delaying the setup
    # of the light base platform.
    hass.async_create_task(profiles.async_initialize(), eager_start=True)

    # Listen for light on and light off service calls.

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up a config entry."""
    if not await hass.data[DATA_COMPONENT].async_setup_entry(entry):
        raise ConfigEntryError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="platform_setup_failed",
            translation_placeholders={"platform": entry.domain, "domain": DOMAIN},
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.data[DATA_COMPONENT].async_unload_entry(entry)


def _coerce_none(value: str) -> None:
    """Coerce an empty string as None."""

    if not isinstance(value, str):
        raise probatio.Invalid("Expected a string")

    if value:
        raise probatio.Invalid("Not an empty string")


@dataclasses.dataclass
class Profile:
    """Representation of a profile.

    The light profiles feature is in a frozen development state
    until otherwise decided in an architecture discussion.
    """

    name: str
    color_x: float | None = dataclasses.field(repr=False)
    color_y: float | None = dataclasses.field(repr=False)
    brightness: int | None
    transition: int | None = None
    hs_color: tuple[float, float] | None = dataclasses.field(init=False)

    SCHEMA = probatio.Schema(
        probatio.Any(
            probatio.ExactSequence(
                (
                    str,
                    probatio.Any(cv.small_float, _coerce_none),
                    probatio.Any(cv.small_float, _coerce_none),
                    probatio.Any(cv.byte, _coerce_none),
                )
            ),
            probatio.ExactSequence(
                (
                    str,
                    probatio.Any(cv.small_float, _coerce_none),
                    probatio.Any(cv.small_float, _coerce_none),
                    probatio.Any(cv.byte, _coerce_none),
                    probatio.Any(VALID_TRANSITION, _coerce_none),
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
    def from_csv_row(cls, csv_row: list[str]) -> Self:
        """Create profile from a CSV row tuple."""
        return cls(*cls.SCHEMA(csv_row))


class Profiles:
    """Representation of available color profiles.

    The light profiles feature is in a frozen development state
    until otherwise decided in an architecture discussion.
    """

    def __init__(self, hass: HomeAssistant) -> None:
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
            with open(profile_path, encoding="utf8") as inp:
                reader = csv.reader(inp)

                # Skip the header
                next(reader, None)

                try:
                    for rec in reader:
                        profile = Profile.from_csv_row(rec)
                        profiles[profile.name] = profile

                except probatio.MultipleInvalid as ex:
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
    def apply_default(
        self, entity_id: str, state_on: bool | None, params: dict[str, Any]
    ) -> None:
        """Return the default profile for the given light."""
        for _entity_id in (entity_id, "group.all_lights"):
            name = f"{_entity_id}.default"
            if name in self.data:
                if not state_on or not params:
                    self.apply_profile(name, params)
                elif self.data[name].transition is not None:
                    params.setdefault(
                        LightServiceArgument.TRANSITION, self.data[name].transition
                    )

    @callback
    def apply_profile(self, name: str, params: dict[str, Any]) -> None:
        """Apply a profile."""
        if (profile := self.data.get(name)) is None:
            return

        color_attributes = (
            LightServiceArgument.COLOR_NAME,
            LightServiceArgument.COLOR_TEMP_KELVIN,
            LightServiceArgument.HS_COLOR,
            LightServiceArgument.RGB_COLOR,
            LightServiceArgument.RGBW_COLOR,
            LightServiceArgument.RGBWW_COLOR,
            LightServiceArgument.XY_COLOR,
            LightServiceArgument.WHITE,
        )

        if profile.hs_color is not None and not any(
            color_attribute in params for color_attribute in color_attributes
        ):
            params[LightServiceArgument.HS_COLOR] = profile.hs_color
        if profile.brightness is not None:
            params.setdefault(LightServiceArgument.BRIGHTNESS, profile.brightness)
        if profile.transition is not None:
            params.setdefault(LightServiceArgument.TRANSITION, profile.transition)
