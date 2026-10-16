"""Provides conditions for weather."""

import asyncio
from collections.abc import Coroutine, Mapping
from datetime import datetime, timedelta
import functools as ft
import logging
from typing import TYPE_CHECKING, Any, Final, Literal, cast, override

import probatio

from homeassistant.const import CONF_OPTIONS, CONF_TARGET
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import (
    ATTR_BEHAVIOR,
    BEHAVIOR_ALL,
    BEHAVIOR_ANY,
    HISTORY_PRIMING_TIMEOUT,
    Condition,
    ConditionConfig,
    EntityConditionBase,
)
from homeassistant.helpers.condition.entity_condition import (
    DATA_HISTORY_PRIMING_MANAGER,
)
from homeassistant.helpers.target import (
    TargetStateChangedData,
    async_track_target_selector_state_change_event,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

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

if TYPE_CHECKING:
    from homeassistant.components.recorder import Recorder

_LOGGER = logging.getLogger(__name__)

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


class _WeatherWindowConditionBase(EntityConditionBase):
    """Base class for conditions that look at a time window."""

    _domain_specs = {DOMAIN: DomainSpec()}

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options
        self._within: timedelta = config.options[CONF_WITHIN]

    @property
    @override
    def needs_polling(self) -> bool:
        """Return True because the window moves with the current time."""
        return True


class DidRainCondition(_WeatherWindowConditionBase):
    """Condition that passes if it rained within a past time window."""

    _schema = DID_RAIN_CONDITION_SCHEMA

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        super().__init__(hass, config)
        # The last time each entity was seen in a rainy state.
        self._last_rain: dict[str, datetime] = {}

    @override
    async def _async_setup(self) -> None:
        """Track when entities stop raining and load recent history."""

        @callback
        def state_changed(data: TargetStateChangedData) -> None:
            event = data.state_change_event
            old_state = event.data["old_state"]
            if old_state is not None and old_state.state in RAINY_CONDITIONS:
                self._set_last_rain(event.data["entity_id"], event.time_fired)

        unsub = await async_track_target_selector_state_change_event(
            self._hass,
            self._target,
            state_changed,
            self.entity_filter,
            self._async_on_entities_update,
            primary_entities_only=self._primary_entities_only,
        )
        self._on_unload.append(unsub)

    @override
    async def _async_on_entities_update(
        self,
        added: set[str],
        removed: set[str],
        _entity_states: Mapping[str, State | None],
    ) -> None:
        """Forget removed entities and load history for added entities."""
        for entity_id in removed:
            self._last_rain.pop(entity_id, None)
        if added and "recorder" in self._hass.config.components:
            await self._async_load_history(added)

    async def _async_load_history(self, entity_ids: set[str]) -> None:
        """Set the last rain time of entities from recorder history."""
        from sqlalchemy.exc import SQLAlchemyError  # noqa: PLC0415

        from homeassistant.components.recorder import history  # noqa: PLC0415

        now = dt_util.utcnow()
        start_time = now - self._within

        async def _read_history(
            instance: Recorder,
        ) -> dict[str, list[State | dict[str, Any]]]:
            return await instance.async_add_executor_job(
                ft.partial(
                    history.get_significant_states,
                    self._hass,
                    start_time,
                    entity_ids=list(entity_ids),
                    include_start_time_state=True,
                    no_attributes=True,
                )
            )

        manager = self._hass.data[DATA_HISTORY_PRIMING_MANAGER]
        try:
            async with asyncio.timeout(HISTORY_PRIMING_TIMEOUT):
                historical_states = await manager.async_prime(_read_history)
        except (SQLAlchemyError, TimeoutError) as err:
            _LOGGER.debug("Error loading rain history: %s", err)
            return

        for entity_id, rows in historical_states.items():
            states = cast(list[State], rows)
            # A state lasts until the next state, or until now for the last one.
            for state, next_state in zip(states, [*states[1:], None], strict=True):
                if state.state in RAINY_CONDITIONS:
                    self._set_last_rain(
                        entity_id,
                        now if next_state is None else next_state.last_changed,
                    )

    def _set_last_rain(self, entity_id: str, last_rain: datetime) -> None:
        """Set the last rain time of an entity if it is later than the known one."""
        if (known := self._last_rain.get(entity_id)) is None or last_rain > known:
            self._last_rain[entity_id] = last_rain

    @override
    def is_valid_state(self, entity_state: State) -> bool:
        """Check if the entity rains now or rained within the window."""
        if entity_state.state in RAINY_CONDITIONS:
            return True
        last_rain = self._last_rain.get(entity_state.entity_id)
        return last_rain is not None and last_rain >= dt_util.utcnow() - self._within


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
        self._forecasts: dict[str, dict[ForecastType, list[dict[str, Any]]]] = {}
        self._subscriptions: dict[str, tuple[WeatherEntity, list[CALLBACK_TYPE]]] = {}

    @override
    async def _async_setup(self) -> None:
        """Subscribe to the forecasts of the targeted entities."""

        @callback
        def state_changed(data: TargetStateChangedData) -> None:
            # The entity object changes when its integration reloads.
            entity_id = data.state_change_event.data["entity_id"]
            if (fetch := self._async_subscribe(entity_id)) is not None:
                self._hass.async_create_task(fetch, eager_start=True)

        self._on_unload.append(self._async_unsubscribe_all)
        unsub = await async_track_target_selector_state_change_event(
            self._hass,
            self._target,
            state_changed,
            self.entity_filter,
            self._async_on_entities_update,
            primary_entities_only=self._primary_entities_only,
        )
        self._on_unload.append(unsub)

    @override
    async def _async_on_entities_update(
        self,
        added: set[str],
        removed: set[str],
        _entity_states: Mapping[str, State | None],
    ) -> None:
        """Subscribe to added entities and unsubscribe from removed entities."""
        for entity_id in removed:
            self._async_unsubscribe(entity_id)
        fetches = [
            fetch
            for entity_id in added
            if (fetch := self._async_subscribe(entity_id)) is not None
        ]
        await asyncio.gather(*fetches)

    @callback
    def _async_subscribe(self, entity_id: str) -> Coroutine[Any, Any, None] | None:
        """Subscribe to the forecasts of an entity.

        Return a coroutine that fetches the first forecasts, or None if there is
        nothing to fetch.
        """
        entity: WeatherEntity | None = None
        if (component := self._hass.data.get(DATA_COMPONENT)) is not None:
            entity = component.get_entity(entity_id)
        if (subscription := self._subscriptions.get(entity_id)) is not None:
            if subscription[0] is entity:
                return None
            self._async_unsubscribe(entity_id)
        if entity is None:
            return None
        supported_features = entity.supported_features or 0
        forecast_types = [
            forecast_type
            for forecast_type, feature in FORECAST_FEATURES.items()
            if supported_features & feature
        ]
        if not forecast_types:
            return None
        self._subscriptions[entity_id] = (
            entity,
            [
                entity.async_subscribe_forecast(
                    forecast_type,
                    ft.partial(self._async_forecast_updated, entity_id, forecast_type),
                )
                for forecast_type in forecast_types
            ],
        )
        return entity.async_update_listeners(forecast_types)

    @callback
    def _async_unsubscribe(self, entity_id: str) -> None:
        """Unsubscribe from the forecasts of an entity."""
        if (subscription := self._subscriptions.pop(entity_id, None)) is not None:
            for unsub in subscription[1]:
                unsub()
        self._forecasts.pop(entity_id, None)

    @callback
    def _async_unsubscribe_all(self) -> None:
        """Unsubscribe from the forecasts of all entities."""
        for entity_id in list(self._subscriptions):
            self._async_unsubscribe(entity_id)

    @callback
    def _async_forecast_updated(
        self,
        entity_id: str,
        forecast_type: ForecastType,
        forecast: list[JsonValueType] | None,
    ) -> None:
        """Store a forecast update."""
        self._forecasts.setdefault(entity_id, {})[forecast_type] = cast(
            list[dict[str, Any]], forecast or []
        )

    def _forecast_in_window(self, entity_id: str) -> list[tuple[float, dict[str, Any]]]:
        """Return the forecast entries in the window.

        Use the finest forecast that covers the whole window. If none does, use
        the forecast that reaches furthest. Each entry comes with the fraction of
        its period that is in the window.
        """
        now = dt_util.utcnow()
        window_end = now + self._within
        best: list[tuple[datetime, datetime, dict[str, Any]]] = []
        for forecast_type, length in FORECAST_PERIODS.items():
            if not (forecast := self._forecasts.get(entity_id, {}).get(forecast_type)):
                continue
            starts = [
                dt_util.parse_datetime(entry[ATTR_FORECAST_TIME], raise_on_error=True)
                for entry in forecast
            ]
            ends = [*starts[1:], starts[-1] + length]
            periods = list(zip(starts, ends, forecast, strict=True))
            if not best or ends[-1] > best[-1][1]:
                best = periods
            if ends[-1] >= window_end:
                break
        entries: list[tuple[float, dict[str, Any]]] = []
        for start, end, entry in best:
            overlap = min(end, window_end) - max(start, now)
            if overlap > timedelta(0):
                entries.append((overlap / (end - start), entry))
        return entries

    @override
    def _should_include(self, _state: State) -> bool:
        """Skip entities without a forecast."""
        return super()._should_include(_state) and any(
            self._forecasts.get(_state.entity_id, {}).values()
        )

    @override
    def is_valid_state(self, entity_state: State) -> bool:
        """Check if the forecast in the window reaches the threshold."""
        entries = self._forecast_in_window(entity_state.entity_id)
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
