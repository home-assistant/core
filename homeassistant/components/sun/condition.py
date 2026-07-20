"""Offer sun based automation rules."""

from datetime import datetime, timedelta
from typing import Any, Unpack, cast, override

import astral.sun
import voluptuous as vol

from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_OPTIONS,
    CONF_TARGET,
    CONF_TYPE,
    DEGREE,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import (
    DomainSpec,
    move_top_level_schema_fields_to_options,
)
from homeassistant.helpers.condition import (
    ATTR_BEHAVIOR,
    BEHAVIOR_ANY,
    Condition,
    ConditionCheckParams,
    ConditionConfig,
    EntityNumericalConditionBase,
    condition_trace_set_result,
    condition_trace_update_result,
)
from homeassistant.helpers.selector import (
    NumericThresholdMode,
    NumericThresholdSelector,
    NumericThresholdSelectorConfig,
)
from homeassistant.helpers.sun import get_astral_event_date, get_astral_observer, is_up
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    ELEVATION_ASTRONOMICAL,
    ELEVATION_CIVIL,
    ELEVATION_HORIZON,
    ELEVATION_NAUTICAL,
    STATE_ATTR_ELEVATION,
)

_OPTIONS_SCHEMA_DICT: dict[vol.Marker, Any] = {
    vol.Optional("before"): cv.sun_event,
    vol.Optional("before_offset"): cv.time_period,
    vol.Optional("after"): cv.sun_event,
    vol.Optional("after_offset"): cv.time_period,
}

_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): vol.All(
            _OPTIONS_SCHEMA_DICT,
            cv.has_at_least_one_key("before", "after"),
        )
    }
)


def sun(
    hass: HomeAssistant,
    before: str | None = None,
    after: str | None = None,
    before_offset: timedelta | None = None,
    after_offset: timedelta | None = None,
) -> bool:
    """Test if current time matches sun requirements."""
    utcnow = dt_util.utcnow()
    today = dt_util.as_local(utcnow).date()
    before_offset = before_offset or timedelta(0)
    after_offset = after_offset or timedelta(0)

    sunrise = get_astral_event_date(hass, SUN_EVENT_SUNRISE, today)
    sunset = get_astral_event_date(hass, SUN_EVENT_SUNSET, today)

    has_sunrise_condition = SUN_EVENT_SUNRISE in (before, after)
    has_sunset_condition = SUN_EVENT_SUNSET in (before, after)

    after_sunrise = sunrise is not None and today > dt_util.as_local(sunrise).date()
    if after_sunrise and has_sunrise_condition:
        tomorrow = today + timedelta(days=1)
        sunrise = get_astral_event_date(hass, SUN_EVENT_SUNRISE, tomorrow)

    after_sunset = sunset is not None and today > dt_util.as_local(sunset).date()
    if after_sunset and has_sunset_condition:
        tomorrow = today + timedelta(days=1)
        sunset = get_astral_event_date(hass, SUN_EVENT_SUNSET, tomorrow)

    # A missing sunrise/sunset means the sun doesn't rise/set on this day, which
    # happens in polar regions.
    if sunrise is None and has_sunrise_condition:
        # There is no sunrise today
        condition_trace_set_result(False, message="no sunrise today")
        return False

    if sunset is None and has_sunset_condition:
        # There is no sunset today
        condition_trace_set_result(False, message="no sunset today")
        return False

    # "before: sunrise" combined with "after: sunset" describes the dark period
    # around midnight, so it is evaluated as an OR (true before sunrise or after
    # sunset) rather than the usual AND of the two bounds.
    if before == SUN_EVENT_SUNRISE and after == SUN_EVENT_SUNSET:
        wanted_time_before = cast(datetime, sunrise) + before_offset
        condition_trace_update_result(wanted_time_before=wanted_time_before)
        wanted_time_after = cast(datetime, sunset) + after_offset
        condition_trace_update_result(wanted_time_after=wanted_time_after)
        return utcnow < wanted_time_before or utcnow > wanted_time_after

    if before == SUN_EVENT_SUNRISE:
        wanted_time_before = cast(datetime, sunrise) + before_offset
        condition_trace_update_result(wanted_time_before=wanted_time_before)
        if utcnow > wanted_time_before:
            return False

    if before == SUN_EVENT_SUNSET:
        wanted_time_before = cast(datetime, sunset) + before_offset
        condition_trace_update_result(wanted_time_before=wanted_time_before)
        if utcnow > wanted_time_before:
            return False

    if after == SUN_EVENT_SUNRISE:
        wanted_time_after = cast(datetime, sunrise) + after_offset
        condition_trace_update_result(wanted_time_after=wanted_time_after)
        if utcnow < wanted_time_after:
            return False

    if after == SUN_EVENT_SUNSET:
        wanted_time_after = cast(datetime, sunset) + after_offset
        condition_trace_update_result(wanted_time_after=wanted_time_after)
        if utcnow < wanted_time_after:
            return False

    return True


class SunCondition(Condition):
    """Sun condition."""

    _options: dict[str, Any]

    @classmethod
    @override
    async def async_validate_complete_config(
        cls, hass: HomeAssistant, complete_config: ConfigType
    ) -> ConfigType:
        """Validate complete config."""
        complete_config = move_top_level_schema_fields_to_options(
            complete_config, _OPTIONS_SCHEMA_DICT
        )
        return await super().async_validate_complete_config(hass, complete_config)

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _CONDITION_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        super().__init__(hass, config)
        assert config.options is not None
        self._options = config.options
        self._before = self._options.get("before")
        self._after = self._options.get("after")
        self._before_offset = self._options.get("before_offset")
        self._after_offset = self._options.get("after_offset")

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        return sun(
            self._hass,
            self._before,
            self._after,
            self._before_offset,
            self._after_offset,
        )


# The sun is a singleton, so these conditions take no target and no options.
_STATE_CONDITION_SCHEMA = vol.Schema({vol.Required(CONF_OPTIONS, default=dict): {}})

# The sun is a singleton, so the elevation condition always targets sun.sun
# instead of asking the user to pick an entity.
_SUN_ENTITY_ID = f"{DOMAIN}.{DOMAIN}"
_ELEVATION_DOMAIN_SPECS = {DOMAIN: DomainSpec(value_source=STATE_ATTR_ELEVATION)}


def _solar_position(hass: HomeAssistant) -> tuple[float, bool]:
    """Return the sun's current elevation in degrees and whether it is rising."""
    observer = get_astral_observer(hass)
    now = dt_util.utcnow()
    elevation = astral.sun.elevation(observer, now)
    rising = astral.sun.elevation(observer, now + timedelta(minutes=1)) > elevation
    return elevation, rising


class _SunStateCondition(Condition):
    """Base class for the option-less sun state conditions."""

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _STATE_CONDITION_SCHEMA(config))


class _UpCondition(_SunStateCondition):
    """Test if the sun is up."""

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        return is_up(self._hass)


class _SetCondition(_SunStateCondition):
    """Test if the sun is set."""

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        return not is_up(self._hass)


class _AscendingCondition(_SunStateCondition):
    """Test if the sun is ascending."""

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        _, rising = _solar_position(self._hass)
        return rising


class _DescendingCondition(_SunStateCondition):
    """Test if the sun is descending."""

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        _, rising = _solar_position(self._hass)
        return not rising


class _NightCondition(_SunStateCondition):
    """Test if it is night (the sun is below all twilight)."""

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        elevation, _ = _solar_position(self._hass)
        return elevation <= ELEVATION_ASTRONOMICAL


_TWILIGHT_ANY = "any"
_TWILIGHT_CIVIL = "civil"
_TWILIGHT_NAUTICAL = "nautical"
_TWILIGHT_ASTRONOMICAL = "astronomical"

# Elevation band (min, max) in degrees for each twilight type, bounded by the
# horizon and the twilight elevations.
_TWILIGHT_BANDS = {
    _TWILIGHT_ANY: (ELEVATION_ASTRONOMICAL, ELEVATION_HORIZON),
    _TWILIGHT_CIVIL: (ELEVATION_CIVIL, ELEVATION_HORIZON),
    _TWILIGHT_NAUTICAL: (ELEVATION_NAUTICAL, ELEVATION_CIVIL),
    _TWILIGHT_ASTRONOMICAL: (ELEVATION_ASTRONOMICAL, ELEVATION_NAUTICAL),
}

_TWILIGHT_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS, default=dict): {
            vol.Optional(CONF_TYPE, default=_TWILIGHT_ANY): vol.In(_TWILIGHT_BANDS),
        }
    }
)


class _TwilightCondition(Condition):
    """Base class for the morning and evening twilight conditions.

    The sun is in twilight when its elevation is within the selected band;
    morning twilight requires the sun to be rising and evening twilight to be
    descending.
    """

    _rising: bool

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _TWILIGHT_CONDITION_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        super().__init__(hass, config)
        assert config.options is not None
        self._low, self._high = _TWILIGHT_BANDS[config.options[CONF_TYPE]]

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        elevation, rising = _solar_position(self._hass)
        return rising == self._rising and self._low <= elevation <= self._high


class _MorningTwilightCondition(_TwilightCondition):
    """Test if it is morning twilight (the sun is rising through twilight)."""

    _rising = True


class _EveningTwilightCondition(_TwilightCondition):
    """Test if it is evening twilight (the sun is descending through twilight)."""

    _rising = False


_ELEVATION_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS, default=dict): {
            vol.Required("threshold"): NumericThresholdSelector(
                NumericThresholdSelectorConfig(mode=NumericThresholdMode.IS)
            ),
        }
    }
)


class _ElevationCondition(EntityNumericalConditionBase):
    """Test the sun's elevation against a threshold."""

    _domain_specs = _ELEVATION_DOMAIN_SPECS
    _valid_unit = DEGREE
    _schema = _ELEVATION_CONDITION_SCHEMA

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config and target the singleton sun entity."""
        config = cast(ConfigType, cls._schema(config))
        config[CONF_TARGET] = {CONF_ENTITY_ID: [_SUN_ENTITY_ID]}
        # `behavior` is needed by `EntityConditionBase.__init__`.
        config[CONF_OPTIONS][ATTR_BEHAVIOR] = BEHAVIOR_ANY
        return config


CONDITIONS: dict[str, type[Condition]] = {
    "_": SunCondition,
    "is_up": _UpCondition,
    "is_set": _SetCondition,
    "is_ascending": _AscendingCondition,
    "is_descending": _DescendingCondition,
    "elevation": _ElevationCondition,
    "is_night": _NightCondition,
    "is_morning_twilight": _MorningTwilightCondition,
    "is_evening_twilight": _EveningTwilightCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the sun conditions."""
    return CONDITIONS
