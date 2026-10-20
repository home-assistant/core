"""Provides functionality to interact with lights."""

import csv
import dataclasses
import logging
import os
from typing import Any, Self, cast, final, override

import probatio
from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (  # noqa: F401
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.frame import ReportBehavior, report_usage
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import color as color_util

from .const import (  # noqa: F401
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
)
from .helper import (  # noqa: F401
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


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
                    params.setdefault(ATTR_TRANSITION, self.data[name].transition)

    @callback
    def apply_profile(self, name: str, params: dict[str, Any]) -> None:
        """Apply a profile."""
        if (profile := self.data.get(name)) is None:
            return

        color_attributes = (
            ATTR_COLOR_NAME,
            ATTR_COLOR_TEMP_KELVIN,
            ATTR_HS_COLOR,
            ATTR_RGB_COLOR,
            ATTR_RGBW_COLOR,
            ATTR_RGBWW_COLOR,
            ATTR_XY_COLOR,
            ATTR_WHITE,
        )

        if profile.hs_color is not None and not any(
            color_attribute in params for color_attribute in color_attributes
        ):
            params[ATTR_HS_COLOR] = profile.hs_color
        if profile.brightness is not None:
            params.setdefault(ATTR_BRIGHTNESS, profile.brightness)
        if profile.transition is not None:
            params.setdefault(ATTR_TRANSITION, profile.transition)


class LightEntityDescription(ToggleEntityDescription, frozen_or_thawed=True):
    """A class that describes binary sensor entities."""


CACHED_PROPERTIES_WITH_ATTR_ = {
    "brightness",
    "color_mode",
    "hs_color",
    "xy_color",
    "rgb_color",
    "rgbw_color",
    "rgbww_color",
    "color_temp_kelvin",
    "min_color_temp_kelvin",
    "max_color_temp_kelvin",
    "effect_list",
    "effect",
    "supported_color_modes",
    "supported_features",
}


class LightEntity(ToggleEntity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for light entities."""

    _entity_component_unrecorded_attributes = frozenset(
        {
            LightEntityCapabilityAttribute.SUPPORTED_COLOR_MODES,
            LightEntityCapabilityAttribute.EFFECT_LIST,
            LightEntityCapabilityAttribute.MIN_COLOR_TEMP_KELVIN,
            LightEntityCapabilityAttribute.MAX_COLOR_TEMP_KELVIN,
            LightEntityStateAttribute.BRIGHTNESS,
            LightEntityStateAttribute.COLOR_MODE,
            LightEntityStateAttribute.COLOR_TEMP_KELVIN,
            LightEntityStateAttribute.EFFECT,
            LightEntityStateAttribute.HS_COLOR,
            LightEntityStateAttribute.RGB_COLOR,
            LightEntityStateAttribute.RGBW_COLOR,
            LightEntityStateAttribute.RGBWW_COLOR,
            LightEntityStateAttribute.XY_COLOR,
        }
    )

    entity_description: LightEntityDescription
    _attr_brightness: int | None = None
    _attr_color_mode: ColorMode | None = None
    _attr_color_temp_kelvin: int | None = None
    _attr_effect_list: list[str] | None = None
    _attr_effect: str | None = None
    _attr_hs_color: tuple[float, float] | None = None
    _attr_max_color_temp_kelvin: int = DEFAULT_MAX_KELVIN
    _attr_min_color_temp_kelvin: int = DEFAULT_MIN_KELVIN
    _attr_rgb_color: tuple[int, int, int] | None = None
    _attr_rgbw_color: tuple[int, int, int, int] | None = None
    _attr_rgbww_color: tuple[int, int, int, int, int] | None = None
    _attr_supported_color_modes: set[ColorMode] | None = None
    _attr_supported_features: LightEntityFeature = LightEntityFeature(0)
    _attr_xy_color: tuple[float, float] | None = None

    @cached_property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return self._attr_brightness

    @cached_property
    def color_mode(self) -> ColorMode | None:
        """Return the color mode of the light."""
        return self._attr_color_mode

    @cached_property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        return self._attr_hs_color

    @cached_property
    def xy_color(self) -> tuple[float, float] | None:
        """Return the xy color value [float, float]."""
        return self._attr_xy_color

    @cached_property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value [int, int, int]."""
        return self._attr_rgb_color

    @cached_property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the rgbw color value [int, int, int, int]."""
        return self._attr_rgbw_color

    @property
    def _light_internal_rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the rgbw color value [int, int, int, int]."""
        return self.rgbw_color

    @cached_property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return the rgbww color value [int, int, int, int, int]."""
        return self._attr_rgbww_color

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the CT color value in Kelvin."""
        return self._attr_color_temp_kelvin

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return the warmest color_temp_kelvin that this light supports."""
        if self._attr_min_color_temp_kelvin is None:
            # For historical reason when both Mired and Kelvin were supported,
            # integrations may have set this explicitly to None.
            # Fallback to DEFAULT to ensure compatibility.
            report_usage(  # type: ignore[unreachable]
                "is explicitly setting `_attr_min_color_temp_kelvin` to `None`, when "
                "it should be setting a valid integer, possibly DEFAULT_MIN_KELVIN ",
                breaks_in_ha_version="2026.8",
                core_behavior=ReportBehavior.LOG,
                integration_domain=self.platform.platform_name
                if self.platform
                else None,
                exclude_integrations={DOMAIN},
            )
            return DEFAULT_MIN_KELVIN
        return self._attr_min_color_temp_kelvin

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return the coldest color_temp_kelvin that this light supports."""
        if self._attr_max_color_temp_kelvin is None:
            # For historical reason when both Mired and Kelvin were supported,
            # integrations may have set this explicitly to None.
            # Fallback to DEFAULT to ensure compatibility.
            report_usage(  # type: ignore[unreachable]
                "is explicitly setting `_attr_max_color_temp_kelvin` to `None`, when "
                "it should be setting a valid integer, possibly DEFAULT_MAX_KELVIN ",
                breaks_in_ha_version="2026.8",
                core_behavior=ReportBehavior.LOG,
                integration_domain=self.platform.platform_name
                if self.platform
                else None,
                exclude_integrations={DOMAIN},
            )
            return DEFAULT_MAX_KELVIN
        return self._attr_max_color_temp_kelvin

    @cached_property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return self._attr_effect_list

    @cached_property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._attr_effect

    @property
    @override
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        data: dict[str, Any] = {}
        supported_features = self.supported_features
        supported_color_modes = self._light_internal_supported_color_modes

        if ColorMode.COLOR_TEMP in supported_color_modes:
            min_color_temp_kelvin = self.min_color_temp_kelvin
            max_color_temp_kelvin = self.max_color_temp_kelvin
            data[LightEntityCapabilityAttribute.MIN_COLOR_TEMP_KELVIN] = (
                min_color_temp_kelvin
            )
            data[LightEntityCapabilityAttribute.MAX_COLOR_TEMP_KELVIN] = (
                max_color_temp_kelvin
            )
        if LightEntityFeature.EFFECT in supported_features:
            data[LightEntityCapabilityAttribute.EFFECT_LIST] = self.effect_list

        data[LightEntityCapabilityAttribute.SUPPORTED_COLOR_MODES] = sorted(
            supported_color_modes
        )

        return data

    def _light_internal_convert_color(
        self, color_mode: ColorMode | str
    ) -> dict[str, tuple[float, ...]]:
        data: dict[str, tuple[float, ...]] = {}
        if color_mode == ColorMode.HS and (hs_color := self.hs_color):
            data[LightEntityStateAttribute.HS_COLOR] = (
                round(hs_color[0], 3),
                round(hs_color[1], 3),
            )
            data[LightEntityStateAttribute.RGB_COLOR] = color_util.color_hs_to_RGB(
                *hs_color
            )
            data[LightEntityStateAttribute.XY_COLOR] = color_util.color_hs_to_xy(
                *hs_color
            )
        elif color_mode == ColorMode.XY and (xy_color := self.xy_color):
            data[LightEntityStateAttribute.HS_COLOR] = color_util.color_xy_to_hs(
                *xy_color
            )
            data[LightEntityStateAttribute.RGB_COLOR] = color_util.color_xy_to_RGB(
                *xy_color
            )
            data[LightEntityStateAttribute.XY_COLOR] = (
                round(xy_color[0], 6),
                round(xy_color[1], 6),
            )
        elif color_mode == ColorMode.RGB and (rgb_color := self.rgb_color):
            data[LightEntityStateAttribute.HS_COLOR] = color_util.color_RGB_to_hs(
                *rgb_color
            )
            data[LightEntityStateAttribute.RGB_COLOR] = tuple(
                int(x) for x in rgb_color[0:3]
            )
            data[LightEntityStateAttribute.XY_COLOR] = color_util.color_RGB_to_xy(
                *rgb_color
            )
        elif color_mode == ColorMode.RGBW and (
            rgbw_color := self._light_internal_rgbw_color
        ):
            rgb_color = color_util.color_rgbw_to_rgb(*rgbw_color)
            data[LightEntityStateAttribute.HS_COLOR] = color_util.color_RGB_to_hs(
                *rgb_color
            )
            data[LightEntityStateAttribute.RGB_COLOR] = tuple(
                int(x) for x in rgb_color[0:3]
            )
            data[LightEntityStateAttribute.RGBW_COLOR] = tuple(
                int(x) for x in rgbw_color[0:4]
            )
            data[LightEntityStateAttribute.XY_COLOR] = color_util.color_RGB_to_xy(
                *rgb_color
            )
        elif color_mode == ColorMode.RGBWW and (rgbww_color := self.rgbww_color):
            rgb_color = color_util.color_rgbww_to_rgb(
                *rgbww_color, self.min_color_temp_kelvin, self.max_color_temp_kelvin
            )
            data[LightEntityStateAttribute.HS_COLOR] = color_util.color_RGB_to_hs(
                *rgb_color
            )
            data[LightEntityStateAttribute.RGB_COLOR] = tuple(
                int(x) for x in rgb_color[0:3]
            )
            data[LightEntityStateAttribute.RGBWW_COLOR] = tuple(
                int(x) for x in rgbww_color[0:5]
            )
            data[LightEntityStateAttribute.XY_COLOR] = color_util.color_RGB_to_xy(
                *rgb_color
            )
        elif color_mode == ColorMode.COLOR_TEMP and (
            color_temp_kelvin := self.color_temp_kelvin
        ):
            hs_color = color_util.color_temperature_to_hs(color_temp_kelvin)
            data[LightEntityStateAttribute.HS_COLOR] = (
                round(hs_color[0], 3),
                round(hs_color[1], 3),
            )
            data[LightEntityStateAttribute.RGB_COLOR] = color_util.color_hs_to_RGB(
                *hs_color
            )
            data[LightEntityStateAttribute.XY_COLOR] = color_util.color_hs_to_xy(
                *hs_color
            )
        return data

    def __validate_color_mode(
        self,
        color_mode: ColorMode | None,
        supported_color_modes: set[ColorMode],
        effect: str | None,
    ) -> None:
        """Validate the color mode."""
        if color_mode is None or color_mode == ColorMode.UNKNOWN:
            # The light is turned off or in an unknown state
            return

        if not effect or effect == EFFECT_OFF:
            # No effect is active, the light must set color mode to one of the supported
            # color modes
            if color_mode in supported_color_modes:
                return
            raise HomeAssistantError(
                f"{self.entity_id} ({type(self)}) set to unsupported color mode "
                f"{color_mode}, expected one of {supported_color_modes}"
            )

        # When an effect is active, the color mode should indicate what adjustments are
        # supported by the effect. To make this possible, we allow the light to set its
        # color mode to on_off, and to brightness if the light allows adjusting
        # brightness, in addition to the otherwise supported color modes.
        effect_color_modes = supported_color_modes | {ColorMode.ONOFF}
        if brightness_supported(effect_color_modes):
            effect_color_modes.add(ColorMode.BRIGHTNESS)

        if color_mode in effect_color_modes:
            return

        raise HomeAssistantError(
            f"{self.entity_id} ({type(self)}) set to unsupported color mode "
            f"{color_mode} when rendering an effect, expected one "
            f"of {effect_color_modes}"
        )

    def __validate_supported_color_modes(
        self,
        supported_color_modes: set[ColorMode],
    ) -> None:
        """Validate the supported color modes."""
        try:
            valid_supported_color_modes(supported_color_modes)
        except probatio.Error as err:
            raise HomeAssistantError(
                f"{self.entity_id} ({type(self)}) sets invalid supported color modes "
                f"{supported_color_modes}"
            ) from err

    @final
    @property
    @override
    def state_attributes(self) -> dict[str, Any] | None:
        """Return state attributes."""
        data: dict[str, Any] = {}
        supported_features = self.supported_features
        supported_color_modes = self._light_internal_supported_color_modes

        _is_on = self.is_on
        color_mode = self.color_mode if _is_on else None
        if _is_on and color_mode is None:
            raise HomeAssistantError(
                f"{self.entity_id} ({type(self)}) does not report a color mode"
            )

        effect: str | None = None
        if LightEntityFeature.EFFECT in supported_features:
            if _is_on:
                effect = self.effect
            data[LightEntityStateAttribute.EFFECT] = effect

        self.__validate_color_mode(color_mode, supported_color_modes, effect)

        data[LightEntityStateAttribute.COLOR_MODE] = color_mode

        if brightness_supported(supported_color_modes):
            if color_mode in COLOR_MODES_BRIGHTNESS:
                data[LightEntityStateAttribute.BRIGHTNESS] = self.brightness
            else:
                data[LightEntityStateAttribute.BRIGHTNESS] = None

        if color_temp_supported(supported_color_modes):
            if color_mode == ColorMode.COLOR_TEMP:
                data[LightEntityStateAttribute.COLOR_TEMP_KELVIN] = (
                    self.color_temp_kelvin
                )
            else:
                data[LightEntityStateAttribute.COLOR_TEMP_KELVIN] = None

        if color_supported(supported_color_modes) or color_temp_supported(
            supported_color_modes
        ):
            data[LightEntityStateAttribute.HS_COLOR] = None
            data[LightEntityStateAttribute.RGB_COLOR] = None
            data[LightEntityStateAttribute.XY_COLOR] = None
            if ColorMode.RGBW in supported_color_modes:
                data[LightEntityStateAttribute.RGBW_COLOR] = None
            if ColorMode.RGBWW in supported_color_modes:
                data[LightEntityStateAttribute.RGBWW_COLOR] = None
            if color_mode:
                data.update(self._light_internal_convert_color(color_mode))

        return data

    @property
    def _light_internal_supported_color_modes(self) -> set[ColorMode]:
        """Get validated supported color modes."""
        if (_supported_color_modes := self.supported_color_modes) is None:
            raise HomeAssistantError(
                f"{self.entity_id} ({type(self)}) does not set supported color modes"
            )
        self.__validate_supported_color_modes(_supported_color_modes)
        return _supported_color_modes

    @cached_property
    def supported_color_modes(self) -> set[ColorMode] | None:
        """Flag supported color modes."""
        return self._attr_supported_color_modes

    @cached_property
    @override
    def supported_features(self) -> LightEntityFeature:
        """Flag supported features."""
        return self._attr_supported_features

    @override
    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the entity."""
        if not self.is_on:
            params = process_turn_on_params(self.hass, self, kwargs)
            if params.get(ATTR_BRIGHTNESS) != 0 and params.get(ATTR_WHITE) != 0:
                await self.async_turn_on(**filter_turn_on_params(self, params))
                return

        params = process_turn_off_params(self.hass, self, kwargs)
        await self.async_turn_off(**filter_turn_off_params(self, params))
