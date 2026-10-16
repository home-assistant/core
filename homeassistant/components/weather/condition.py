"""Provides conditions for weather."""

import asyncio
from datetime import datetime, timedelta
import functools as ft
from typing import TYPE_CHECKING, Any, Final, Literal, Unpack, cast, override

import probatio

from homeassistant.const import (
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State, split_entity_id
from homeassistant.exceptions import ConditionErrorMessage
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import (
    ATTR_BEHAVIOR,
    BEHAVIOR_ALL,
    BEHAVIOR_ANY,
    Condition,
    ConditionCheckParams,
    ConditionConfig,
)
from homeassistant.helpers.recorder import get_instance
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from . import (
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TIME,
    WeatherEntity,
    WeatherEntityFeature,
)
from .const import DATA_COMPONENT, DOMAIN

CONF_MEASURE: Final = "measure"
CONF_THRESHOLD: Final = "threshold"
CONF_WITHIN: Final = "within"

MEASURE_AMOUNT: Final = "amount"
MEASURE_PROBABILITY: Final = "probability"

RAINY_CONDITIONS: Final = frozenset(
    {
        ATTR_CONDITION_LIGHTNING_RAINY,
        ATTR_CONDITION_POURING,
        ATTR_CONDITION_RAINY,
        ATTR_CONDITION_SNOWY_RAINY,
    }
)

type ForecastType = Literal["hourly", "twice_daily", "daily"]

# Finest first. The length of a period is the time to the next entry, or this
# length for the last entry.
FORECAST_PERIODS: Final[dict[ForecastType, timedelta]] = {
    "hourly": timedelta(hours=1),
    "twice_daily": timedelta(hours=12),
    "daily": timedelta(days=1),
}
FORECAST_FEATURES: Final[dict[ForecastType, WeatherEntityFeature]] = {
    "hourly": WeatherEntityFeature.FORECAST_HOURLY,
    "twice_daily": WeatherEntityFeature.FORECAST_TWICE_DAILY,
    "daily": WeatherEntityFeature.FORECAST_DAILY,
}

_OPTIONS_SCHEMA_DICT: dict[probatio.Marker, Any] = {
    probatio.Required(ATTR_BEHAVIOR, default=BEHAVIOR_ANY): probatio.In(
        [BEHAVIOR_ANY, BEHAVIOR_ALL]
    ),
    probatio.Required(CONF_WITHIN): cv.positive_time_period,
}

DID_RAIN_CONDITION_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_TARGET): cv.TARGET_FIELDS,
        probatio.Required(CONF_OPTIONS): _OPTIONS_SCHEMA_DICT,
    }
)

WILL_RAIN_CONDITION_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_TARGET): cv.TARGET_FIELDS,
        probatio.Required(CONF_OPTIONS): {
            **_OPTIONS_SCHEMA_DICT,
            probatio.Required(CONF_MEASURE, default=MEASURE_AMOUNT): probatio.In(
                [MEASURE_AMOUNT, MEASURE_PROBABILITY]
            ),
            probatio.Required(CONF_THRESHOLD): probatio.All(
                probatio.Coerce(float), probatio.Range(min=0)
            ),
        },
    }
)


class _WeatherWindowConditionBase(Condition):
    """Base class for conditions that look at a time window."""

    _schema: probatio.Schema

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, cls._schema(config))

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.target
            assert config.options
        self._target_selection = TargetSelection(config.target)
        self._matcher = any if config.options[ATTR_BEHAVIOR] == BEHAVIOR_ANY else all
        self._within: timedelta = config.options[CONF_WITHIN]

    def _targeted_states(self) -> list[State]:
        """Return the states of the targeted weather entities."""
        targeted = async_extract_referenced_entity_ids(
            self._hass, self._target_selection, expand_group=False
        )
        return [
            state
            for entity_id in targeted.referenced | targeted.indirectly_referenced
            if split_entity_id(entity_id)[0] == DOMAIN
            and (state := self._hass.states.get(entity_id)) is not None
            and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ]

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Refuse a check that cannot fetch data."""
        raise ConditionErrorMessage(
            DOMAIN, "this condition must fetch data and cannot be checked here"
        )


class DidRainCondition(_WeatherWindowConditionBase):
    """Condition that passes if it rained within a past time window."""

    _schema = DID_RAIN_CONDITION_SCHEMA

    @override
    async def _async_evaluate(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check if the entities rain now or rained within the window."""
        states = self._targeted_states()
        rained = await self._async_rained(
            [state.entity_id for state in states if state.state not in RAINY_CONDITIONS]
        )
        return self._matcher(
            state.state in RAINY_CONDITIONS or state.entity_id in rained
            for state in states
        )

    async def _async_rained(self, entity_ids: list[str]) -> set[str]:
        """Return the entities that recorder history shows as rainy in the window."""
        if not entity_ids:
            return set()
        if "recorder" not in self._hass.config.components:
            raise ConditionErrorMessage(DOMAIN, "the recorder is not available")

        from homeassistant.components.recorder import history  # noqa: PLC0415

        historical_states = await get_instance(self._hass).async_add_executor_job(
            ft.partial(
                history.get_significant_states,
                self._hass,
                dt_util.utcnow() - self._within,
                entity_ids=entity_ids,
                include_start_time_state=True,
                no_attributes=True,
            )
        )
        return {
            entity_id
            for entity_id, rows in historical_states.items()
            if any(cast(State, row).state in RAINY_CONDITIONS for row in rows)
        }


class WillRainCondition(_WeatherWindowConditionBase):
    """Condition that passes if rain is forecast within a future time window."""

    _schema = WILL_RAIN_CONDITION_SCHEMA

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options
        self._measure: str = config.options[CONF_MEASURE]
        self._threshold: float = config.options[CONF_THRESHOLD]

    @override
    async def _async_evaluate(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Check if the forecasts in the window reach the threshold."""
        if (component := self._hass.data.get(DATA_COMPONENT)) is None:
            return self._matcher([])
        entities = [
            entity
            for state in self._targeted_states()
            if (entity := component.get_entity(state.entity_id)) is not None
        ]
        forecasts = await asyncio.gather(
            *(self._async_forecast_in_window(entity) for entity in entities)
        )
        return self._matcher(
            self._reaches_threshold(forecast)
            for forecast in forecasts
            if forecast is not None
        )

    async def _async_forecast_in_window(
        self, entity: WeatherEntity
    ) -> list[tuple[float, dict[str, Any]]] | None:
        """Return the forecast entries in the window, or None without a forecast.

        Use the finest forecast that covers the whole window. If none does, use
        the forecast that reaches furthest. Each entry comes with the fraction of
        its period that is in the window.
        """
        now = dt_util.utcnow()
        window_end = now + self._within
        supported_features = entity.supported_features or 0
        best: list[tuple[datetime, datetime, dict[str, Any]]] | None = None
        for forecast_type, length in FORECAST_PERIODS.items():
            if not supported_features & FORECAST_FEATURES[forecast_type]:
                continue
            native_forecast = await getattr(entity, f"async_forecast_{forecast_type}")()
            if not native_forecast:
                continue
            forecast = cast(
                list[dict[str, Any]],
                entity._convert_forecast(native_forecast),  # noqa: SLF001
            )
            starts = [
                dt_util.parse_datetime(entry[ATTR_FORECAST_TIME], raise_on_error=True)
                for entry in forecast
            ]
            ends = [*starts[1:], starts[-1] + length]
            if best is None or ends[-1] > best[-1][1]:
                best = list(zip(starts, ends, forecast, strict=True))
            if ends[-1] >= window_end:
                break
        if best is None:
            return None
        return [
            ((min(end, window_end) - max(start, now)) / (end - start), entry)
            for start, end, entry in best
            if min(end, window_end) > max(start, now)
        ]

    def _reaches_threshold(self, entries: list[tuple[float, dict[str, Any]]]) -> bool:
        """Check if the forecast entries reach the threshold."""
        if self._measure == MEASURE_AMOUNT:
            amount: float = sum(
                fraction * entry[ATTR_FORECAST_PRECIPITATION]
                for fraction, entry in entries
                if entry.get(ATTR_FORECAST_PRECIPITATION) is not None
            )
            return amount >= self._threshold
        return any(
            entry[ATTR_FORECAST_PRECIPITATION_PROBABILITY] >= self._threshold
            for _, entry in entries
            if entry.get(ATTR_FORECAST_PRECIPITATION_PROBABILITY) is not None
        )


CONDITIONS: dict[str, type[Condition]] = {
    "did_rain": DidRainCondition,
    "will_rain": WillRainCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the weather conditions."""
    return CONDITIONS
