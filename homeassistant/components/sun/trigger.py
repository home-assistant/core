"""Provides triggers for the sun."""

from datetime import datetime, timedelta
from typing import Any, cast, override

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
_SUN_EVENT_SOLAR_NOON = "noon"
_SUN_EVENT_SOLAR_MIDNIGHT = "midnight"
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
    """Trigger that fires at a solar event time."""

    _event: str
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

    def _run_context(self) -> str:
        """Return a short description of the trigger for the action run context."""
        return f"sun event {self._event}"

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
            run_action(self._action_payload(), self._run_context())

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
    both (firing at whichever comes next).

    ``_event`` is not an astral event here (the scheduling is done in
    ``_get_next_event``); it is only the label reported as ``trigger.description``.
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

    _event = "golden_hour_started"
    _rising_elevation = ELEVATION_GOLDEN_HOUR_LOW
    _setting_elevation = ELEVATION_GOLDEN_HOUR_HIGH


class GoldenHourEndedTrigger(_GoldenBlueHourTrigger):
    """Trigger that fires when golden hour ends."""

    _event = "golden_hour_ended"
    _rising_elevation = ELEVATION_GOLDEN_HOUR_HIGH
    _setting_elevation = ELEVATION_GOLDEN_HOUR_LOW


class BlueHourStartedTrigger(_GoldenBlueHourTrigger):
    """Trigger that fires when blue hour starts."""

    _event = "blue_hour_started"
    _rising_elevation = ELEVATION_BLUE_HOUR_LOW
    _setting_elevation = ELEVATION_BLUE_HOUR_HIGH


class BlueHourEndedTrigger(_GoldenBlueHourTrigger):
    """Trigger that fires when blue hour ends."""

    _event = "blue_hour_ended"
    _rising_elevation = ELEVATION_BLUE_HOUR_HIGH
    _setting_elevation = ELEVATION_BLUE_HOUR_LOW


def _next_horizon_crossing(
    observer: astral.Observer,
    event: str,
    utc_point_in_time: datetime,
    target_above: bool,
    offset: timedelta,
) -> datetime | None:
    """Return the next solar noon/midnight where the sun crosses the horizon.

    ``event`` is ``midnight`` (the midnight sun is defined by the sun's daily low)
    or ``noon`` (the polar night by its daily high). ``target_above`` selects the
    crossing direction: ``True`` finds the day the elevation first rises above the
    horizon, ``False`` the day it first drops below. Returns ``None`` when no such
    crossing occurs within the scanned window (just over a year), which is the
    case at any latitude that never has a midnight sun or polar night.
    """
    event_func = getattr(astral.sun, event)
    # Start two days back so the very next crossing has a prior sample to compare.
    # The window is a bit over a year so that, when rescheduling from just inside
    # a period, the next year's crossing is still found.
    local_date = dt_util.as_local(utc_point_in_time).date() - timedelta(days=2)
    prev_above: bool | None = None
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

    ``_solar_event`` is the astral event scanned for the crossing; ``_event`` is
    only the label reported as ``trigger.description``.
    """

    _solar_event: str
    _target_above: bool

    @override
    def _get_next_event(self, utc_point_in_time: datetime) -> datetime | None:
        return _next_horizon_crossing(
            get_astral_observer(self._hass),
            self._solar_event,
            utc_point_in_time,
            self._target_above,
            self._offset,
        )


class MidnightSunStartedTrigger(_MidnightSunPolarNightTrigger):
    """Trigger that fires when the midnight sun period starts."""

    _event = "midnight_sun_started"
    _solar_event = _SUN_EVENT_SOLAR_MIDNIGHT
    _target_above = True


class MidnightSunEndedTrigger(_MidnightSunPolarNightTrigger):
    """Trigger that fires when the midnight sun period ends."""

    _event = "midnight_sun_ended"
    _solar_event = _SUN_EVENT_SOLAR_MIDNIGHT
    _target_above = False


class PolarNightStartedTrigger(_MidnightSunPolarNightTrigger):
    """Trigger that fires when the polar night period starts."""

    _event = "polar_night_started"
    _solar_event = _SUN_EVENT_SOLAR_NOON
    _target_above = False


class PolarNightEndedTrigger(_MidnightSunPolarNightTrigger):
    """Trigger that fires when the polar night period ends."""

    _event = "polar_night_ended"
    _solar_event = _SUN_EVENT_SOLAR_NOON
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
