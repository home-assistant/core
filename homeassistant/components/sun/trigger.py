"""Provides triggers for the sun."""

from datetime import datetime, timedelta
from typing import Any, Final, Literal, cast, override

import astral.sun
import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_EVENT,
    CONF_FOR,
    CONF_OFFSET,
    CONF_OPTIONS,
    CONF_TYPE,
    DEGREE,
    EVENT_CORE_CONFIG_UPDATE,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import (
    DomainSpec,
    move_top_level_schema_fields_to_options,
)
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.selector import (
    NumericThresholdMode,
    NumericThresholdSelector,
    NumericThresholdSelectorConfig,
)
from homeassistant.helpers.sun import (
    get_astral_event_next,
    get_astral_observer,
    get_observer_astral_event_next,
)
from homeassistant.helpers.trigger import (
    EntityNumericalStateChangedTriggerBase,
    EntityNumericalStateCrossedThresholdTriggerBase,
    EntityNumericalStateTriggerBase,
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)
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

# Names of solar events supported by the astral.sun module
_SUN_EVENT_SOLAR_NOON: Final = "noon"
_SUN_EVENT_SOLAR_MIDNIGHT: Final = "midnight"
_SUN_EVENT_DAWN = "dawn"
_SUN_EVENT_DUSK = "dusk"

_TWILIGHT_CIVIL = "civil"
_TWILIGHT_NAUTICAL = "nautical"
_TWILIGHT_ASTRONOMICAL = "astronomical"

CONF_PERIOD = "period"
_PERIOD_ANY = "any"
_PERIOD_MORNING = "morning"
_PERIOD_EVENING = "evening"
_PERIODS = (_PERIOD_ANY, _PERIOD_MORNING, _PERIOD_EVENING)

CONF_OFFSET_TYPE = "offset_type"
OFFSET_TYPE_BEFORE = "before"
OFFSET_TYPE_AFTER = "after"

# Offset options shared by the solar event triggers. A positive offset combined
# with an offset type of "before" fires earlier than the event; "after" later.
_OFFSET_OPTIONS: dict[vol.Marker, Any] = {
    vol.Required(CONF_OFFSET, default=timedelta(0)): cv.time_period,
    vol.Required(CONF_OFFSET_TYPE, default=OFFSET_TYPE_BEFORE): vol.In(
        {OFFSET_TYPE_BEFORE, OFFSET_TYPE_AFTER}
    ),
}

# Sun elevation at each twilight boundary.
_TWILIGHT_ELEVATIONS = {
    _TWILIGHT_CIVIL: ELEVATION_CIVIL,
    _TWILIGHT_NAUTICAL: ELEVATION_NAUTICAL,
    _TWILIGHT_ASTRONOMICAL: ELEVATION_ASTRONOMICAL,
}

# The sun is a singleton, so the elevation triggers always target sun.sun
# instead of asking the user to pick an entity.
_SUN_ENTITY_ID = f"{DOMAIN}.{DOMAIN}"
_ELEVATION_DOMAIN_SPECS = {DOMAIN: DomainSpec(value_source=STATE_ATTR_ELEVATION)}

_ELEVATION_CHANGED_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS, default=dict): {
            vol.Required("threshold"): NumericThresholdSelector(
                NumericThresholdSelectorConfig(mode=NumericThresholdMode.CHANGED)
            ),
        }
    }
)

# Unlike the generic numerical triggers there is no behavior option: a behavior
# (each/first/all) is only meaningful across multiple targeted entities.
_ELEVATION_CROSSED_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS, default=dict): {
            vol.Required("threshold"): NumericThresholdSelector(
                NumericThresholdSelectorConfig(mode=NumericThresholdMode.CROSSED)
            ),
            vol.Optional(CONF_FOR): cv.positive_time_period,
        }
    }
)


class SunElevationTrigger(EntityNumericalStateTriggerBase):
    """Trigger for the sun's elevation."""

    _domain_specs = _ELEVATION_DOMAIN_SPECS
    _valid_unit = DEGREE

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger, targeting the singleton sun entity."""
        super().__init__(
            hass,
            TriggerConfig(
                key=config.key,
                target={ATTR_ENTITY_ID: [_SUN_ENTITY_ID]},
                options=config.options,
            ),
        )


class SunElevationChangedTrigger(
    SunElevationTrigger, EntityNumericalStateChangedTriggerBase
):
    """Trigger for changes to the sun's elevation."""

    _schema = _ELEVATION_CHANGED_TRIGGER_SCHEMA


class SunElevationCrossedTrigger(
    SunElevationTrigger, EntityNumericalStateCrossedThresholdTriggerBase
):
    """Trigger for the sun's elevation crossing a threshold."""

    _schema = _ELEVATION_CROSSED_TRIGGER_SCHEMA


_EVENT_TRIGGER_SCHEMA = vol.Schema(
    {vol.Required(CONF_OPTIONS, default=dict): {**_OFFSET_OPTIONS}}
)


class SunEventTrigger(Trigger):
    """Trigger that fires at a solar event time.

    ``_event`` is the astral event the trigger schedules on. ``trigger.description``
    defaults to ``sun event {_event}``; a subclass whose scheduling is not a single
    astral event sets ``_context`` to name itself there instead.
    """

    _event: str
    _context: str | None = None
    _schema: vol.Schema = _EVENT_TRIGGER_SCHEMA

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, cls._schema(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        self._options = config.options or {}
        offset = self._options.get(CONF_OFFSET) or timedelta(0)
        if self._options.get(CONF_OFFSET_TYPE) == OFFSET_TYPE_BEFORE:
            offset = -offset
        self._offset = offset

    def _get_next_event(self, utc_point_in_time: datetime) -> datetime | None:
        """Return the next time this solar event occurs.

        Subclasses may return ``None`` when the event never occurs at the current
        location (e.g. a midnight sun trigger outside the polar regions), in which
        case the trigger stays armed but unscheduled until the location changes.
        """
        return get_astral_event_next(
            self._hass, self._event, utc_point_in_time, self._offset
        )

    def _action_payload(self) -> dict[str, Any]:
        """Return extra trigger payload passed to the action."""
        return {}

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        unsubs: dict[str, CALLBACK_TYPE | None] = {"event": None, "config": None}

        @callback
        def schedule_next_event() -> None:
            next_event = self._get_next_event(dt_util.utcnow())
            if next_event is None:
                return
            unsubs["event"] = async_track_point_in_utc_time(
                self._hass, handle_event, next_event
            )

        @callback
        def handle_event(_now: datetime) -> None:
            unsubs["event"] = None
            schedule_next_event()
            run_action(
                self._action_payload(), f"sun event {self._context or self._event}"
            )

        @callback
        def handle_config(_event: Event) -> None:
            if unsubs["event"]:
                unsubs["event"]()
            schedule_next_event()

        unsubs["config"] = self._hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, handle_config
        )
        schedule_next_event()

        @callback
        def async_remove() -> None:
            for unsub in unsubs.values():
                if unsub:
                    unsub()

        return async_remove


class SunriseTrigger(SunEventTrigger):
    """Trigger that fires at sunrise."""

    _event = SUN_EVENT_SUNRISE


class SunsetTrigger(SunEventTrigger):
    """Trigger that fires at sunset."""

    _event = SUN_EVENT_SUNSET


class SolarNoonTrigger(SunEventTrigger):
    """Trigger that fires at solar noon."""

    _event = _SUN_EVENT_SOLAR_NOON


class SolarMidnightTrigger(SunEventTrigger):
    """Trigger that fires at solar midnight."""

    _event = _SUN_EVENT_SOLAR_MIDNIGHT


_DAWN_DUSK_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS, default=dict): {
            vol.Optional(CONF_TYPE, default=_TWILIGHT_CIVIL): vol.In(
                _TWILIGHT_ELEVATIONS
            ),
            **_OFFSET_OPTIONS,
        }
    }
)


class SunDawnDuskTrigger(SunEventTrigger):
    """Trigger that fires at dawn or dusk for a configurable twilight phase."""

    _schema = _DAWN_DUSK_TRIGGER_SCHEMA

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        self._twilight: str = self._options[CONF_TYPE]
        self._elevation = _TWILIGHT_ELEVATIONS[self._twilight]

    @override
    def _get_next_event(self, utc_point_in_time: datetime) -> datetime:
        return get_observer_astral_event_next(
            get_astral_observer(self._hass),
            self._event,
            utc_point_in_time,
            self._offset,
            # astral takes a depression (degrees below the horizon), i.e. the
            # negated elevation.
            depression=-self._elevation,
        )

    @override
    def _action_payload(self) -> dict[str, Any]:
        return {CONF_TYPE: self._twilight}


class DawnTrigger(SunDawnDuskTrigger):
    """Trigger that fires at dawn."""

    _event = _SUN_EVENT_DAWN


class DuskTrigger(SunDawnDuskTrigger):
    """Trigger that fires at dusk."""

    _event = _SUN_EVENT_DUSK


_GOLDEN_BLUE_HOUR_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS, default=dict): {
            vol.Optional(CONF_PERIOD, default=_PERIOD_ANY): vol.In(_PERIODS),
            **_OFFSET_OPTIONS,
        }
    }
)


class _GoldenBlueHourTrigger(SunEventTrigger):
    """Trigger that fires at a golden or blue hour boundary crossing.

    Each boundary is a solar elevation the sun crosses twice a day: once while
    rising (the morning crossing) and once while descending (the evening one).
    The rising crossing is found as a ``dawn`` at the boundary elevation and the
    descending crossing as a ``dusk``; ``period`` selects morning, evening, or
    both (firing at whichever comes next). There is no single astral ``_event``;
    scheduling is done in ``_get_next_event`` and ``_context`` names the trigger.
    """

    _rising_elevation: float
    _setting_elevation: float
    _schema = _GOLDEN_BLUE_HOUR_TRIGGER_SCHEMA

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        self._period: str = self._options[CONF_PERIOD]

    @override
    def _get_next_event(self, utc_point_in_time: datetime) -> datetime | None:
        observer = get_astral_observer(self._hass)
        crossings: list[tuple[str, float]] = []
        if self._period in (_PERIOD_ANY, _PERIOD_MORNING):
            crossings.append((_SUN_EVENT_DAWN, self._rising_elevation))
        if self._period in (_PERIOD_ANY, _PERIOD_EVENING):
            crossings.append((_SUN_EVENT_DUSK, self._setting_elevation))

        next_events: list[datetime] = []
        for event, elevation in crossings:
            try:
                next_events.append(
                    get_observer_astral_event_next(
                        observer,
                        event,
                        utc_point_in_time,
                        self._offset,
                        # astral takes a depression (degrees below the horizon),
                        # i.e. the negated elevation.
                        depression=-elevation,
                    )
                )
            except ValueError:
                # The sun never reaches this boundary at the current latitude
                # (e.g. during a polar night); ignore this crossing.
                continue
        if next_events:
            return min(next_events)
        return None

    @override
    def _action_payload(self) -> dict[str, Any]:
        return {CONF_PERIOD: self._period}


class GoldenHourStartedTrigger(_GoldenBlueHourTrigger):
    """Trigger that fires when golden hour starts."""

    _context = "golden_hour_started"
    _rising_elevation = ELEVATION_GOLDEN_HOUR_LOW
    _setting_elevation = ELEVATION_GOLDEN_HOUR_HIGH


class GoldenHourEndedTrigger(_GoldenBlueHourTrigger):
    """Trigger that fires when golden hour ends."""

    _context = "golden_hour_ended"
    _rising_elevation = ELEVATION_GOLDEN_HOUR_HIGH
    _setting_elevation = ELEVATION_GOLDEN_HOUR_LOW


class BlueHourStartedTrigger(_GoldenBlueHourTrigger):
    """Trigger that fires when blue hour starts."""

    _context = "blue_hour_started"
    _rising_elevation = ELEVATION_BLUE_HOUR_LOW
    _setting_elevation = ELEVATION_BLUE_HOUR_HIGH


class BlueHourEndedTrigger(_GoldenBlueHourTrigger):
    """Trigger that fires when blue hour ends."""

    _context = "blue_hour_ended"
    _rising_elevation = ELEVATION_BLUE_HOUR_HIGH
    _setting_elevation = ELEVATION_BLUE_HOUR_LOW


# A midnight sun or polar night - the sun's daily extreme staying above / below
# the horizon - only happens inside the polar circles. Under the same apparent
# elevation vs ELEVATION_HORIZON test the sun entity uses for its above/below
# horizon state, a midnight sun first becomes possible at ~65.4° of latitude (a
# polar night higher still), so below this the scan never finds a crossing and is
# skipped. 65.0° stays a safe margin under that minimum.
_MIN_POLAR_LATITUDE = 65.0


def _next_polar_transition(
    observer: astral.Observer,
    event: Literal["noon", "midnight"],
    utc_point_in_time: datetime,
    target_above: bool,
    offset: timedelta,
) -> datetime | None:
    """Return the next solar noon/midnight that starts or ends a polar period.

    A midnight sun or polar night begins/ends at the solar midnight/noon whose
    elevation crosses the horizon. ``event`` is ``midnight`` (the midnight sun is
    bounded by the sun's daily low) or ``noon`` (the polar night by its daily
    high); ``target_above`` selects the crossing direction - ``True`` for the day
    the extreme first rises above the horizon, ``False`` for the day it first
    drops below. Returns ``None`` when no such crossing exists, which is the case
    at any latitude that never has a midnight sun or polar night: there the sun
    rises and sets every day, so the solar midnight stays below and the solar noon
    above the horizon and neither ever crosses it.
    """
    # Outside the polar circles neither event can occur; skip the ~year-long scan
    # (which would otherwise run in the event loop on every scheduling attempt).
    if abs(observer.latitude) < _MIN_POLAR_LATITUDE:
        return None

    event_func = getattr(astral.sun, event)
    # The fire time is event_time + offset, so a crossing only matters once its
    # event_time passes utc_point_in_time - offset (the same threshold the
    # fire-time guard applies below). Anchoring the scan there - two days back for
    # the first crossing's prior sample - covers the relevant crossings for either
    # offset sign: a positive ("after") offset reaches back to a crossing whose
    # delayed fire is still pending, a negative ("before") offset forward to one
    # whose advanced fire has not yet arrived. The window stays bounded regardless
    # of the offset magnitude.
    anchor = utc_point_in_time - offset
    local_date = dt_util.as_local(anchor).date() - timedelta(days=2)
    prev_above: bool | None = None
    # A couple of days of prior samples plus a bit over a year, so the next annual
    # crossing is always reached (e.g. when rescheduling from inside a period).
    for _ in range(400):
        event_time: datetime = event_func(observer, local_date)
        above = astral.sun.elevation(observer, event_time) > ELEVATION_HORIZON
        if (
            prev_above is not None
            and above == target_above
            and above != prev_above
            and (fire_time := event_time + offset) > utc_point_in_time
        ):
            return fire_time
        prev_above = above
        local_date += timedelta(days=1)
    return None


class _MidnightSunPolarNightTrigger(SunEventTrigger):
    """Trigger for the start or end of the midnight sun or polar night.

    The transition happens at the solar noon or midnight whose elevation crosses
    the horizon: the midnight sun starts/ends when the sun's daily low (solar
    midnight) rises above/drops below the horizon, and the polar night when its
    daily high (solar noon) drops below/rises above it.

    The daily solar extreme is used rather than the actual sunrise/sunset event
    because astral's rise/set calculations are numerically unstable where the sun
    only grazes the horizon, and a polar night has no sunrise/sunset event at all
    (its sun clears the horizon around noon, not at a normal sunrise). Firing at
    the extreme places the event where the sun is unambiguously up or down.

    ``_event`` is the astral solar extreme scanned for the crossing; ``_context``
    names the trigger for ``trigger.description``.
    """

    _event: Literal["noon", "midnight"]
    _target_above: bool

    @override
    def _get_next_event(self, utc_point_in_time: datetime) -> datetime | None:
        return _next_polar_transition(
            get_astral_observer(self._hass),
            self._event,
            utc_point_in_time,
            self._target_above,
            self._offset,
        )


class MidnightSunStartedTrigger(_MidnightSunPolarNightTrigger):
    """Trigger that fires when the midnight sun period starts."""

    _event = _SUN_EVENT_SOLAR_MIDNIGHT
    _context = "midnight_sun_started"
    _target_above = True


class MidnightSunEndedTrigger(_MidnightSunPolarNightTrigger):
    """Trigger that fires when the midnight sun period ends."""

    _event = _SUN_EVENT_SOLAR_MIDNIGHT
    _context = "midnight_sun_ended"
    _target_above = False


class PolarNightStartedTrigger(_MidnightSunPolarNightTrigger):
    """Trigger that fires when the polar night period starts."""

    _event = _SUN_EVENT_SOLAR_NOON
    _context = "polar_night_started"
    _target_above = False


class PolarNightEndedTrigger(_MidnightSunPolarNightTrigger):
    """Trigger that fires when the polar night period ends."""

    _event = _SUN_EVENT_SOLAR_NOON
    _context = "polar_night_ended"
    _target_above = True


_LEGACY_OPTIONS_SCHEMA_DICT: dict[vol.Marker, Any] = {
    vol.Required(CONF_EVENT): cv.sun_event,
    vol.Optional(CONF_OFFSET, default=timedelta(0)): cv.time_period,
}


class LegacySunTrigger(SunEventTrigger):
    """Backwards compatible trigger for the legacy ``platform: sun`` config."""

    _schema = vol.Schema({vol.Required(CONF_OPTIONS): _LEGACY_OPTIONS_SCHEMA_DICT})

    @override
    @classmethod
    async def async_validate_complete_config(
        cls, hass: HomeAssistant, complete_config: ConfigType
    ) -> ConfigType:
        """Validate complete config, migrating the legacy top-level fields."""
        complete_config = move_top_level_schema_fields_to_options(
            complete_config, _LEGACY_OPTIONS_SCHEMA_DICT
        )
        return await super().async_validate_complete_config(hass, complete_config)

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        self._event = self._options[CONF_EVENT]

    @override
    def _action_payload(self) -> dict[str, Any]:
        return {"event": self._event, "offset": self._offset}


TRIGGERS: dict[str, type[Trigger]] = {
    "_": LegacySunTrigger,
    "sunrise": SunriseTrigger,
    "sunset": SunsetTrigger,
    "solar_noon": SolarNoonTrigger,
    "solar_midnight": SolarMidnightTrigger,
    "dawn": DawnTrigger,
    "dusk": DuskTrigger,
    "golden_hour_started": GoldenHourStartedTrigger,
    "golden_hour_ended": GoldenHourEndedTrigger,
    "blue_hour_started": BlueHourStartedTrigger,
    "blue_hour_ended": BlueHourEndedTrigger,
    "midnight_sun_started": MidnightSunStartedTrigger,
    "midnight_sun_ended": MidnightSunEndedTrigger,
    "polar_night_started": PolarNightStartedTrigger,
    "polar_night_ended": PolarNightEndedTrigger,
    "elevation_changed": SunElevationChangedTrigger,
    "elevation_crossed_threshold": SunElevationCrossedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for the sun."""
    return TRIGGERS
