"""Entity conditions."""

import abc
import asyncio
from collections.abc import Callable, Coroutine, Mapping
from datetime import datetime, timedelta
import functools as ft
import logging
from typing import TYPE_CHECKING, Any, ClassVar, Final, Unpack, cast, override

import probatio

from homeassistant.const import (
    CONF_FOR,
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityStateAttribute,
)
from homeassistant.core import HomeAssistant, State, callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import (
    DomainSpec,
    ThresholdConfig,
    filter_by_domain_specs,
)
from homeassistant.helpers.recorder import get_instance
from homeassistant.helpers.selector import (
    NumericThresholdMode,
    NumericThresholdSelector,
    NumericThresholdSelectorConfig,
    NumericThresholdType,
)
from homeassistant.helpers.target import (
    TargetSelection,
    TargetStateChangedData,
    async_extract_referenced_entity_ids,
    async_track_target_selector_state_change_event,
)
from homeassistant.helpers.typing import UNDEFINED, ConfigType, UndefinedType
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.unit_conversion import BaseUnitConverter

if TYPE_CHECKING:
    from homeassistant.components.recorder import Recorder

from .models import Condition, ConditionCheckParams, ConditionConfig

_LOGGER = logging.getLogger(__name__)

# Upper bound on the best-effort recorder query used to prime `for:` durations
# at setup. If history can't be read within this window we fall back to the
# conservative live-state anchor rather than blocking condition setup.
HISTORY_PRIMING_TIMEOUT = 10

# How far back the `for:` priming query reaches. Caps the cost of the query for
# very long `for:` durations; beyond this we rely on the live-state anchor, so
# such conditions may only become true once enough time has elapsed since setup.
MAX_HISTORY_PRIMING_LOOKBACK = timedelta(hours=6)

ATTR_BEHAVIOR: Final = "behavior"
BEHAVIOR_ANY: Final = "any"
BEHAVIOR_ALL: Final = "all"

ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL = probatio.Schema(
    {
        probatio.Required(CONF_TARGET): cv.TARGET_FIELDS,
        probatio.Required(CONF_OPTIONS, default={}): {
            probatio.Required(ATTR_BEHAVIOR, default=BEHAVIOR_ANY): probatio.In(
                [BEHAVIOR_ANY, BEHAVIOR_ALL]
            ),
            probatio.Optional(CONF_FOR): cv.positive_time_period,
        },
    }
)


class EntityConditionBase(Condition):
    """Base class for entity conditions."""

    _domain_specs: Mapping[str, DomainSpec]
    _excluded_states: Final[frozenset[str]] = frozenset(
        {STATE_UNAVAILABLE, STATE_UNKNOWN}
    )
    _schema: probatio.Schema = ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL
    # When True, indirect target expansion (via device/area/floor) skips
    # entities with an entity_category.
    _primary_entities_only: ClassVar[bool] = True

    @override
    @classmethod
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
        self._target = config.target
        self._target_selection = TargetSelection(config.target)
        self._behavior = config.options[ATTR_BEHAVIOR]
        self._duration: timedelta | None = config.options.get(CONF_FOR)
        if self._behavior == BEHAVIOR_ANY:
            self._matcher = self._check_any_match_state
        elif self._behavior == BEHAVIOR_ALL:
            self._matcher = self._check_all_match_state
        self._on_unload: list[Callable[[], None]] = []
        self._valid_since: dict[str, datetime] = {}
        # Entities whose `for:` anchor is currently being resolved from recorder
        # history. While an entity is here the live listener leaves its anchor to
        # the priming, except that an invalidation removes it (the run broke, so
        # the in-flight history is stale and live tracking takes over).
        self._priming: set[str] = set()

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Filter entities matching any of the domain specs."""
        return filter_by_domain_specs(self._hass, self._domain_specs, entities)

    @property
    def _needs_duration_tracking(self) -> bool:
        """Whether this condition needs active state change tracking for duration.

        The base implementation intentionally defaults to always tracking
        duration and should be overridden by subclasses that can safely use
        state.last_changed directly. For example, conditions that are true
        for a single main state value may not need active tracking, while
        conditions that track attributes or match multiple states do because
        last_changed does not capture those transitions.
        """
        return True

    def _state_valid_since(self, _state: State) -> datetime:
        """Return the datetime that anchors `for:` durations for `state`.

        Override in subclasses whose `is_valid_state` reads
        attributes directly without going through `value_source`.
        """
        if self._domain_specs[_state.domain].value_source is None:
            return _state.last_changed
        return _state.last_updated

    def _update_valid_since(self, entity_id: str, _state: State | None) -> None:
        """Update _valid_since tracking for an entity based on its current state.

        If the entity is in a valid state and not already tracked, records
        when the condition became true (via `_state_valid_since`). If the
        entity is not in a valid state, removes it from tracking.
        """
        if (
            _state is not None
            and self._should_include(_state)
            and self.is_valid_state(_state)
        ):
            # While an entity is being primed from history, leave its anchor to
            # the priming: the entity stayed valid, so the run is unbroken and the
            # history start (which can be earlier than this update) is accurate.
            if entity_id in self._priming:
                return
            # Only record the time if not already tracked, to avoid
            # resetting the duration on unrelated state/attribute updates.
            if entity_id not in self._valid_since:
                self._valid_since[entity_id] = self._state_valid_since(_state)
        else:
            # An invalidation breaks the run, so any history being loaded for the
            # entity is now stale; stop priming it and let live tracking own it.
            self._priming.discard(entity_id)
            self._valid_since.pop(entity_id, None)

    @override
    async def _async_setup(self) -> None:
        """Set up state tracking for duration-based conditions."""
        if not self._duration or not self._needs_duration_tracking:
            return

        @callback
        def _state_change_listener(
            data: TargetStateChangedData,
        ) -> None:
            """Track when entities enter or leave a valid state."""
            event = data.state_change_event
            entity_id = event.data["entity_id"]
            to_state = event.data["new_state"]

            self._update_valid_since(entity_id, to_state)

        unsub = await async_track_target_selector_state_change_event(
            self._hass,
            self._target,
            _state_change_listener,
            self.entity_filter,
            self._async_on_entities_update,
            primary_entities_only=self._primary_entities_only,
        )
        self._on_unload.append(unsub)

    async def _async_on_entities_update(
        self,
        added: set[str],
        removed: set[str],
        _entity_states: Mapping[str, State | None],
    ) -> None:
        """Handle changes to the tracked entity set.

        Removed entities stop being tracked immediately. Added entities are only
        considered by the condition once their `for:` anchor has been resolved
        (see `_async_prime_valid_since`); until then they are absent from
        `_valid_since`. The target tracker awaits this for the initial entity set
        at setup and runs it as a background task for later registry-driven
        changes.
        """
        for entity_id in removed:
            self._priming.discard(entity_id)
            self._valid_since.pop(entity_id, None)
        await self._async_prime_valid_since(added)

    async def _async_prime_valid_since(self, entity_ids: set[str]) -> None:
        """Resolve and store the `for:` anchor for newly tracked entities.

        For each currently-valid entity the anchor is the start of its current
        continuous run of validity, read from recorder history (bounded by
        `MAX_HISTORY_PRIMING_LOOKBACK`). The earlier of that and the current
        state's own anchor wins, so a run that began before the lookback window
        is not cut short. When the recorder is unavailable or the read fails,
        the current state's anchor is used alone. An entity is added to
        `_valid_since` only once this resolves, so a newly tracked entity does
        not participate in the condition until its anchor is known — rather than
        briefly using a conservative anchor that then changes.

        While loading, an entity is held in `_priming`. A live change that keeps
        it valid is ignored (the run is unbroken, history is accurate), but an
        invalidation removes it from `_priming` so that we do not apply now-stale
        history over the live tracking that observed the break.
        """
        # Conservative anchor from the live state for each currently-valid entity.
        anchors = {
            entity_id: self._state_valid_since(_state)
            for entity_id in entity_ids
            if (_state := self._hass.states.get(entity_id)) is not None
            and self._should_include(_state)
            and self.is_valid_state(_state)
        }
        if not anchors:
            return

        self._priming.update(anchors)
        try:
            if "recorder" in self._hass.config.components:
                await self._async_refine_anchors_from_history(anchors)
            for entity_id, anchor in anchors.items():
                # Skip entities a live change invalidated mid-load: they were
                # removed from `_priming`, the run broke, and live tracking (which
                # saw the break) owns them — applying this history would be stale.
                if entity_id in self._priming:
                    self._valid_since[entity_id] = anchor
        finally:
            self._priming.difference_update(anchors)

    async def _async_refine_anchors_from_history(
        self, anchors: dict[str, datetime]
    ) -> None:
        """Move each anchor in `anchors` back to the true start of its run.

        For each entity the anchor becomes the earlier of the recorded run start
        and the existing (live) anchor; entities with no usable history keep
        their existing anchor. Mutates `anchors` in place.
        """
        from sqlalchemy.exc import SQLAlchemyError  # noqa: PLC0415

        from homeassistant.components.recorder import history  # noqa: PLC0415

        if TYPE_CHECKING:
            assert self._duration is not None
        lookback = min(self._duration, MAX_HISTORY_PRIMING_LOOKBACK)
        start_time = dt_util.utcnow() - lookback

        async def _read_history(
            instance: Recorder,
        ) -> dict[str, list[State | dict[str, Any]]]:
            # The history query only sees committed rows; the priming manager
            # flushes the recorder queue before running this.
            return await instance.async_add_executor_job(
                ft.partial(
                    history.get_significant_states,
                    self._hass,
                    start_time,
                    entity_ids=list(anchors),
                    include_start_time_state=True,
                    # Mandatory: the default (True) drops attribute-only changes
                    # for entities outside SIGNIFICANT_DOMAINS, which are exactly
                    # the transitions attribute-based conditions depend on.
                    significant_changes_only=False,
                    minimal_response=False,
                )
            )

        manager = self._hass.data[DATA_HISTORY_PRIMING_MANAGER]
        try:
            # The timeout also covers waiting for our turn, so under a flood of
            # primings a condition falls back to its conservative anchor rather
            # than blocking on the queue indefinitely.
            async with asyncio.timeout(HISTORY_PRIMING_TIMEOUT):
                historical_states = await manager.async_prime(_read_history)
        except (SQLAlchemyError, TimeoutError) as err:
            # Best effort: keep the conservative anchors rather than failing.
            _LOGGER.debug("Error priming condition durations from history: %s", err)
            return

        for entity_id, rows in historical_states.items():
            valid_since = self._valid_since_from_history(
                entity_id, cast(list[State], rows)
            )
            if valid_since is not None:
                anchors[entity_id] = min(valid_since, anchors[entity_id])

    def _valid_since_from_history(
        self, entity_id: str, rows: list[State]
    ) -> datetime | None:
        """Return when the current continuous run of valid states began.

        Walks recorded states newest-first and stops at the first one that is
        not valid; the anchor is the oldest state in the unbroken run leading up
        to the latest recorded state. (We can't just take the first valid state
        in the window: an intervening invalid period breaks the run, so the
        anchor must come from after it.) Returns None when the latest recorded
        state is not valid, e.g. the recorder lags behind the live state machine.
        """
        # Recorder rows are LazyState objects, which skip State.__init__ and so
        # never populate the domain/object_id that the validity checks rely on.
        domain, object_id = split_entity_id(entity_id)
        valid_since: datetime | None = None
        for _state in reversed(rows):
            _state.domain = domain
            _state.object_id = object_id
            if not (self._should_include(_state) and self.is_valid_state(_state)):
                break
            valid_since = self._state_valid_since(_state)
        return valid_since

    @override
    def _async_unload(self) -> None:
        """Unsubscribe from listeners."""
        for cb in self._on_unload:
            cb()
        self._on_unload.clear()

    def _should_include(self, _state: State) -> bool:
        """Check if an entity should participate in any/all checks.

        The default implementation excludes only entities whose state.state
        is in `_excluded_states` (unavailable / unknown). Subclasses can
        override to also exclude entities that lack the optional capability
        the condition relies on.
        """
        return _state.state not in self._excluded_states

    @abc.abstractmethod
    def is_valid_state(self, entity_state: State) -> bool:
        """Check if the state matches the expected state(s)."""

    def _check_any_match_state(self, states: list[State]) -> bool:
        """Test if any entity matches the state."""
        if not self._duration:
            # Skip duration check if duration is not specified or 0
            return any(self.is_valid_state(state) for state in states)
        cutoff = dt_util.utcnow() - self._duration
        if not self._needs_duration_tracking:
            return any(
                self.is_valid_state(state) and state.last_changed <= cutoff
                for state in states
            )
        return any(
            self.is_valid_state(state)
            and (valid_since := self._valid_since.get(state.entity_id)) is not None
            and valid_since <= cutoff
            for state in states
        )

    def _check_all_match_state(self, states: list[State]) -> bool:
        """Test if all entities match the state."""
        if not self._duration:
            # Skip duration check if duration is not specified or 0
            return all(self.is_valid_state(state) for state in states)
        cutoff = dt_util.utcnow() - self._duration
        if not self._needs_duration_tracking:
            return all(
                self.is_valid_state(state) and state.last_changed <= cutoff
                for state in states
            )
        return all(
            self.is_valid_state(state)
            and (valid_since := self._valid_since.get(state.entity_id)) is not None
            and valid_since <= cutoff
            for state in states
        )

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Test state condition."""
        targeted_entities = async_extract_referenced_entity_ids(
            self._hass,
            self._target_selection,
            expand_group=False,
            primary_entities_only=self._primary_entities_only,
        )
        referenced_entity_ids = targeted_entities.referenced.union(
            targeted_entities.indirectly_referenced
        )
        filtered_entity_ids = self.entity_filter(referenced_entity_ids)
        entity_states = [
            _state
            for entity_id in filtered_entity_ids
            if (_state := self._hass.states.get(entity_id))
            and self._should_include(_state)
        ]
        return self._matcher(entity_states)


class EntityStateConditionBase(EntityConditionBase):
    """State condition."""

    _states: set[str | bool]

    @property
    @override
    def _needs_duration_tracking(self) -> bool:
        """Single-state conditions with no attribute tracking can use last_changed."""
        if len(self._states) != 1:
            return True
        return any(
            spec.value_source is not None for spec in self._domain_specs.values()
        )

    def _get_tracked_value(self, entity_state: State) -> Any:
        """Get the tracked value from a state based on the DomainSpec."""
        domain_spec = self._domain_specs[entity_state.domain]
        if domain_spec.value_source is None:
            return entity_state.state
        return entity_state.attributes.get(domain_spec.value_source)

    @override
    def is_valid_state(self, entity_state: State) -> bool:
        """Check if the state matches the expected state(s)."""
        return self._get_tracked_value(entity_state) in self._states


def _normalize_domain_specs(
    domain_specs: Mapping[str, DomainSpec] | str,
) -> Mapping[str, DomainSpec]:
    """Normalize domain_specs argument to a Mapping."""
    if isinstance(domain_specs, str):
        return {domain_specs: DomainSpec()}
    return domain_specs


def make_entity_state_condition(
    domain_specs: Mapping[str, DomainSpec] | str,
    states: str | bool | set[str | bool],
    *,
    primary_entities_only: bool = True,
) -> type[EntityStateConditionBase]:
    """Create a condition for entity state changes to specific state(s).

    domain_specs can be a string (domain name) for simple state-based conditions,
    or a Mapping[str, DomainSpec] for attribute-based or multi-domain conditions.
    """
    specs = _normalize_domain_specs(domain_specs)

    if isinstance(states, (str, bool)):
        states_set: set[str | bool] = {states}
    else:
        states_set = states

    class CustomCondition(EntityStateConditionBase):
        """Condition for entity state."""

        _domain_specs = specs
        _states = states_set
        _primary_entities_only = primary_entities_only

    return CustomCondition


NUMERICAL_CONDITION_SCHEMA = ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL.extend(
    {
        probatio.Required(CONF_OPTIONS): {
            probatio.Required("threshold"): NumericThresholdSelector(
                NumericThresholdSelectorConfig(mode=NumericThresholdMode.IS)
            ),
        },
    }
)


class EntityNumericalConditionBase(EntityConditionBase):
    """Condition for numerical state comparisons with above/below thresholds."""

    _schema = NUMERICAL_CONDITION_SCHEMA
    _valid_unit: str | UndefinedType | None = UNDEFINED

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize the numerical condition."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options is not None
        threshold_options: dict[str, Any] = config.options["threshold"]
        self.threshold = ThresholdConfig.from_config(threshold_options.get("value"))
        self.lower_threshold = ThresholdConfig.from_config(
            threshold_options.get("value_min")
        )
        self.upper_threshold = ThresholdConfig.from_config(
            threshold_options.get("value_max")
        )
        self._threshold_type = threshold_options["type"]

    def _is_valid_unit(self, unit: str | None) -> bool:
        """Check if the given unit is valid for this condition."""
        if isinstance(self._valid_unit, UndefinedType):
            return True
        return unit == self._valid_unit

    def _get_threshold_value(self, threshold: ThresholdConfig | None) -> float | None:
        """Get threshold value from float or entity state."""
        if threshold is None:
            return None
        if threshold.numerical:
            return threshold.number

        if not (entity_state := self._hass.states.get(threshold.entity)):  # type: ignore[arg-type]
            # Entity not found
            return None
        if not self._is_valid_unit(
            entity_state.attributes.get(EntityStateAttribute.UNIT_OF_MEASUREMENT)
        ):
            # Entity unit does not match the expected unit
            return None
        try:
            return float(entity_state.state)
        except TypeError, ValueError:
            # Entity state is not a valid number
            return None

    def _get_tracked_value(self, entity_state: State) -> Any:
        """Get the tracked value from a state.

        Includes unit validation for state-based values.
        """
        domain_spec = self._domain_specs[entity_state.domain]
        if domain_spec.value_source is None:
            if not self._is_valid_unit(
                entity_state.attributes.get(EntityStateAttribute.UNIT_OF_MEASUREMENT)
            ):
                return None
            return entity_state.state
        return entity_state.attributes.get(domain_spec.value_source)

    @override
    def is_valid_state(self, entity_state: State) -> bool:
        """Check if the state is within the specified range."""
        try:
            value = float(self._get_tracked_value(entity_state))
        except TypeError, ValueError:
            return False

        if self._threshold_type == NumericThresholdType.ABOVE:
            if (limit := self._get_threshold_value(self.threshold)) is None:
                # Entity not found or invalid number, don't trigger
                return False
            return value > limit
        if self._threshold_type == NumericThresholdType.BELOW:
            if (limit := self._get_threshold_value(self.threshold)) is None:
                # Entity not found or invalid number, don't trigger
                return False
            return value < limit

        # Mode is BETWEEN or OUTSIDE
        lower_limit = self._get_threshold_value(self.lower_threshold)
        upper_limit = self._get_threshold_value(self.upper_threshold)
        if lower_limit is None or upper_limit is None:
            # Entity not found or invalid number, don't trigger
            return False
        between = lower_limit <= value <= upper_limit
        if self._threshold_type == NumericThresholdType.BETWEEN:
            return between
        return not between


def make_entity_numerical_condition(
    domain_specs: Mapping[str, DomainSpec] | str,
    valid_unit: str | UndefinedType | None = UNDEFINED,
    *,
    primary_entities_only: bool = True,
) -> type[EntityNumericalConditionBase]:
    """Create a condition for numerical state comparisons."""
    specs = _normalize_domain_specs(domain_specs)

    class CustomCondition(EntityNumericalConditionBase):
        """Condition for numerical state."""

        _domain_specs = specs
        _valid_unit = valid_unit
        _primary_entities_only = primary_entities_only

    return CustomCondition


def _make_numerical_condition_with_unit_schema(
    unit_converter: type[BaseUnitConverter],
) -> probatio.Schema:
    """Factory for numerical condition schema with unit option."""
    return ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL.extend(
        {
            probatio.Required(CONF_OPTIONS): {
                probatio.Required("threshold"): NumericThresholdSelector(
                    NumericThresholdSelectorConfig(
                        mode=NumericThresholdMode.IS,
                        unit_of_measurement=list(unit_converter.VALID_UNITS),
                    )
                ),
            },
        }
    )


class EntityNumericalConditionWithUnitBase(EntityNumericalConditionBase):
    """Condition for numerical state comparisons with unit conversion."""

    _base_unit: str | None  # Base unit for the tracked value
    _unit_converter: type[BaseUnitConverter]

    @override
    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Create a schema."""
        super().__init_subclass__(**kwargs)
        cls._schema = _make_numerical_condition_with_unit_schema(cls._unit_converter)

    def _get_entity_unit(self, entity_state: State) -> str | None:
        """Get the unit of an entity from its state."""
        return entity_state.attributes.get(EntityStateAttribute.UNIT_OF_MEASUREMENT)

    @override
    def _get_threshold_value(self, threshold: ThresholdConfig | None) -> float | None:
        """Get threshold value from float or entity state."""
        if threshold is None:
            return None
        if threshold.numerical:
            return self._unit_converter.convert(
                threshold.number,  # type: ignore[arg-type]
                threshold.unit,  # type: ignore[arg-type]
                self._base_unit,
            )

        if not (entity_state := self._hass.states.get(threshold.entity)):  # type: ignore[arg-type]
            # Entity not found
            return None
        try:
            value = float(entity_state.state)
        except TypeError, ValueError:
            # Entity state is not a valid number
            return None

        try:
            return self._unit_converter.convert(
                value,
                entity_state.attributes.get(EntityStateAttribute.UNIT_OF_MEASUREMENT),
                self._base_unit,
            )
        except HomeAssistantError:
            # Unit conversion failed (i.e. incompatible units), treat as invalid number
            return None

    @override
    def _get_tracked_value(self, entity_state: State) -> Any:
        """Get the tracked numerical value from a state."""
        domain_spec = self._domain_specs[entity_state.domain]
        raw_value: Any
        if domain_spec.value_source is None:
            raw_value = entity_state.state
        else:
            raw_value = entity_state.attributes.get(domain_spec.value_source)

        try:
            value = float(raw_value)
        except TypeError, ValueError:
            return None

        try:
            return self._unit_converter.convert(
                value, self._get_entity_unit(entity_state), self._base_unit
            )
        except HomeAssistantError:
            return None


def make_entity_numerical_condition_with_unit(
    domain_specs: Mapping[str, DomainSpec],
    base_unit: str,
    unit_converter: type[BaseUnitConverter],
) -> type[EntityNumericalConditionWithUnitBase]:
    """Create a condition for numerical state comparisons with unit conversion."""

    class CustomCondition(EntityNumericalConditionWithUnitBase):
        """Condition for numerical state with unit conversion."""

        _domain_specs = domain_specs
        _base_unit = base_unit
        _unit_converter = unit_converter

    return CustomCondition


DATA_HISTORY_PRIMING_MANAGER: HassKey[HistoryPrimingManager] = HassKey(
    "condition_history_priming_manager"
)


class HistoryPrimingManager:
    """Serialize and coalesce the recorder reads that prime condition durations.

    At startup many conditions may prime at once. Letting each hit the recorder
    independently would force a separate commit per condition and run every read
    on the shared DB executor in parallel — a flood. So the reads run one at a
    time, and a single commit flush is shared by each "generation" of conditions
    that arrive while the previous flush is running.

    The flush a condition relies on must begin after that condition started
    tracking its entities, or the read could miss a change still queued in the
    recorder and compute too generous an anchor. A condition therefore never
    relies on a flush that was already running when it arrived (the lobby); it
    waits that one out and joins the next, re-attempting if the flush it waited
    for was cancelled before completing. This mirrors `ReloadServiceHelper`
    minus its target de-duplication, which does not apply because each condition
    reads its own entities.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the manager."""
        self._hass = hass
        self._flush_condition = asyncio.Condition()
        self._flushing = False
        self._flush_ok = False
        self._query_lock = asyncio.Lock()

    async def async_prime[_T](
        self, job: Callable[[Recorder], Coroutine[Any, Any, _T]]
    ) -> _T:
        """Flush the recorder, then run `job`, coordinated with other primings."""
        await self._async_flush()
        async with self._query_lock:
            return await job(get_instance(self._hass))

    async def _async_flush(self) -> None:
        """Return once a recorder flush that began no earlier than this call ends.

        The first condition of a generation performs the flush; the rest rely on
        it.
        """
        async with self._flush_condition:
            # Lobby: a flush already running began before we arrived, so it may
            # not capture our entity's queued changes. Wait it out, don't rely on
            # it.
            if self._flushing:
                await self._flush_condition.wait()

        while True:
            async with self._flush_condition:
                if not self._flushing:
                    # First past the lobby this generation: we run the flush.
                    self._flushing = True
                    break
                # A peer began a fresh flush after we cleared the lobby; wait for
                # it.
                await self._flush_condition.wait()
                if self._flush_ok:
                    return
                # The flush we waited for was cancelled before completing (its owner
                # timed out): loop and start or wait for a fresh one rather than read
                # against a queue that was never flushed.

        instance = get_instance(self._hass)
        flushed = False
        try:
            if (commit_future := instance.async_get_commit_future()) is not None:
                await commit_future
            flushed = True
        finally:
            async with self._flush_condition:
                self._flushing = False
                self._flush_ok = flushed
                self._flush_condition.notify_all()
