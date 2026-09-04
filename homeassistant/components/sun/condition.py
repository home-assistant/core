"""Offer sun based automation rules."""

from datetime import datetime, timedelta
from typing import Any, Final, Literal, Unpack, cast, override

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
    ELEVATION_BLUE_HOUR_HIGH,
    ELEVATION_BLUE_HOUR_LOW,
    ELEVATION_CIVIL,
    ELEVATION_GOLDEN_HOUR_HIGH,
    ELEVATION_GOLDEN_HOUR_LOW,
    ELEVATION_HORIZON,
    ELEVATION_NAUTICAL,
    STATE_ATTR_ELEVATION,
)

# Names of the solar noon/midnight events in the astral.sun module.
_SUN_EVENT_SOLAR_NOON: Final = "noon"
_SUN_EVENT_SOLAR_MIDNIGHT: Final = "midnight"

CONF_PERIOD = "period"
_PERIOD_ANY = "any"
_PERIOD_MORNING = "morning"
_PERIOD_EVENING = "evening"
_PERIODS = (_PERIOD_ANY, _PERIOD_MORNING, _PERIOD_EVENING)

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


_PERIOD_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS, default=dict): {
            vol.Optional(CONF_PERIOD, default=_PERIOD_ANY): vol.In(_PERIODS),
        }
    }
)


class _GoldenBlueHourCondition(Condition):
    """Base class for the golden and blue hour conditions.

    The sun is in golden/blue hour when its elevation is within the band; the
    ``period`` option narrows this to the rising (morning) or descending
    (evening) pass through the band.
    """

    _low: float
    _high: float

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _PERIOD_CONDITION_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        super().__init__(hass, config)
        assert config.options is not None
        self._period = config.options[CONF_PERIOD]

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        elevation, rising = _solar_position(self._hass)
        if not self._low <= elevation <= self._high:
            return False
        if self._period == _PERIOD_MORNING:
            return rising
        if self._period == _PERIOD_EVENING:
            return not rising
        return True


class _GoldenHourCondition(_GoldenBlueHourCondition):
    """Test if it is golden hour."""

    _low = ELEVATION_GOLDEN_HOUR_LOW
    _high = ELEVATION_GOLDEN_HOUR_HIGH


class _BlueHourCondition(_GoldenBlueHourCondition):
    """Test if it is blue hour."""

    _low = ELEVATION_BLUE_HOUR_LOW
    _high = ELEVATION_BLUE_HOUR_HIGH


def _elevation_at_last_solar_extreme(
    hass: HomeAssistant, event: Literal["noon", "midnight"]
) -> float:
    """Return the sun's elevation at the most recent solar noon or midnight.

    Evaluating the current cycle's extreme (the one at or before now), rather than
    the next one, keeps ``is_midnight_sun``/``is_polar_night`` in step with their
    start/end triggers: those fire at the solar noon/midnight whose elevation
    crosses the horizon, and looking ahead would flip the condition up to a day
    early.
    """
    observer = get_astral_observer(hass)
    now = dt_util.utcnow()
    event_func = getattr(astral.sun, event)
    # Scan a short window and keep the latest extreme at or before now. Starting
    # two days back guarantees the first candidate precedes now even for time
    # zones skewed far from their meridian.
    local_date = dt_util.as_local(now).date() - timedelta(days=2)
    latest: datetime = event_func(observer, local_date)
    for _ in range(4):
        local_date += timedelta(days=1)
        candidate: datetime = event_func(observer, local_date)
        if candidate <= now:
            latest = candidate
        else:
            # Candidates only move later, so the first one past now ends the scan.
            break
    elevation: float = astral.sun.elevation(observer, latest)
    return elevation


class _MidnightSunCondition(_SunStateCondition):
    """Test if it is midnight sun (the sun stays above the horizon for 24h)."""

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        # The sun's daily low is at solar midnight; if even that is above the
        # horizon the sun never sets during this cycle.
        elevation = _elevation_at_last_solar_extreme(
            self._hass, _SUN_EVENT_SOLAR_MIDNIGHT
        )
        return elevation > ELEVATION_HORIZON


class _PolarNightCondition(_SunStateCondition):
    """Test if it is polar night (the sun stays below the horizon for 24h)."""

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check the condition."""
        # The sun's daily high is at solar noon; if even that is below the
        # horizon the sun never rises during this cycle.
        elevation = _elevation_at_last_solar_extreme(self._hass, _SUN_EVENT_SOLAR_NOON)
        return elevation < ELEVATION_HORIZON


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
    "is_golden_hour": _GoldenHourCondition,
    "is_blue_hour": _BlueHourCondition,
    "is_midnight_sun": _MidnightSunCondition,
    "is_polar_night": _PolarNightCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the sun conditions."""
    return CONDITIONS
