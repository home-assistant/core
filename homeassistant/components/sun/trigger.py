"""Provides triggers for the sun."""

from datetime import datetime, timedelta
from typing import Any, cast, override

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
    ELEVATION_CIVIL,
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


_EVENT_TRIGGER_SCHEMA = vol.Schema({vol.Required(CONF_OPTIONS, default=dict): {}})


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

    def _get_next_event(self, utc_point_in_time: datetime) -> datetime:
        """Return the next time this solar event occurs."""
        return get_astral_event_next(self._hass, self._event, utc_point_in_time)

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
            unsubs["event"] = async_track_point_in_utc_time(
                self._hass, handle_event, self._get_next_event(dt_util.utcnow())
            )

        @callback
        def handle_event(_now: datetime) -> None:
            unsubs["event"] = None
            schedule_next_event()
            run_action(self._action_payload(), f"sun event {self._event}")

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
        self._offset: timedelta = self._options[CONF_OFFSET]

    @override
    def _get_next_event(self, utc_point_in_time: datetime) -> datetime:
        return get_astral_event_next(
            self._hass, self._event, utc_point_in_time, self._offset
        )

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
    "elevation_changed": SunElevationChangedTrigger,
    "elevation_crossed_threshold": SunElevationCrossedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for the sun."""
    return TRIGGERS
