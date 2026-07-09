"""Offer reusable conditions."""

import abc
import asyncio
from collections import deque
from collections.abc import Callable, Container, Coroutine, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta
import functools as ft
import inspect
import logging
import re
import sys
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Final,
    Literal,
    Never,
    Protocol,
    TypedDict,
    Unpack,
    cast,
    final,
    overload,
    override,
)

import voluptuous as vol

from homeassistant.const import (
    CONF_ABOVE,
    CONF_AFTER,
    CONF_ATTRIBUTE,
    CONF_BEFORE,
    CONF_BELOW,
    CONF_CONDITION,
    CONF_DEVICE_ID,
    CONF_ENABLED,
    CONF_ENTITY_ID,
    CONF_FOR,
    CONF_ID,
    CONF_MATCH,
    CONF_OPTIONS,
    CONF_SELECTOR,
    CONF_STATE,
    CONF_TARGET,
    CONF_VALUE_TEMPLATE,
    CONF_WEEKDAY,
    CONF_ZONE,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_ANY,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    WEEKDAYS,
    EntityStateAttribute,
)
from homeassistant.core import (
    HomeAssistant,
    State,
    callback,
    split_entity_id,
    valid_entity_id,
)
from homeassistant.exceptions import (
    ConditionError,
    ConditionErrorContainer,
    ConditionErrorIndex,
    ConditionErrorMessage,
    HomeAssistantError,
    TemplateError,
)
from homeassistant.loader import (
    Integration,
    IntegrationNotFound,
    async_get_integration,
    async_get_integrations,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.unit_conversion import BaseUnitConverter
from homeassistant.util.yaml import load_yaml_dict

from . import config_validation as cv, entity_registry as er, selector
from .automation import (
    DomainSpec,
    ThresholdConfig,
    filter_by_domain_specs,
    get_absolute_description_key,
    get_relative_description_key,
    move_options_fields_to_top_level,
)
from .integration_platform import async_process_integration_platforms
from .recorder import get_instance
from .selector import (
    NumericThresholdMode,
    NumericThresholdSelector,
    NumericThresholdSelectorConfig,
    NumericThresholdType,
    TargetSelector,
)
from .target import (
    TargetSelection,
    TargetStateChangedData,
    async_extract_referenced_entity_ids,
    async_track_target_selector_state_change_event,
)
from .template import Template, render_complex
from .trace import (
    TraceElement,
    trace_append_element,
    trace_path,
    trace_path_get,
    trace_stack_cv,
    trace_stack_pop,
    trace_stack_push,
    trace_stack_top,
)
from .typing import UNDEFINED, ConfigType, TemplateVarsType, UndefinedType

if TYPE_CHECKING:
    from homeassistant.components.recorder import Recorder

ASYNC_FROM_CONFIG_FORMAT = "async_{}_from_config"
FROM_CONFIG_FORMAT = "{}_from_config"
VALIDATE_CONFIG_FORMAT = "{}_validate_config"

_LOGGER = logging.getLogger(__name__)

# Upper bound on the best-effort recorder query used to prime `for:` durations
# at setup. If history can't be read within this window we fall back to the
# conservative live-state anchor rather than blocking condition setup.
HISTORY_PRIMING_TIMEOUT = 10

# How far back the `for:` priming query reaches. Caps the cost of the query for
# very long `for:` durations; beyond this we rely on the live-state anchor, so
# such conditions may only become true once enough time has elapsed since setup.
MAX_HISTORY_PRIMING_LOOKBACK = timedelta(hours=6)

_PLATFORM_ALIASES: dict[str | None, str | None] = {
    "and": None,
    "device": "device_automation",
    "not": None,
    "numeric_state": None,
    "or": None,
    "state": None,
    "template": None,
    "time": None,
    "trigger": None,
}

INPUT_ENTITY_ID = re.compile(
    r"^input_(?:select|text|number|boolean|datetime)\.(?!.+__)(?!_)[\da-z_]+(?<!_)$"
)


CONDITION_DESCRIPTION_CACHE: HassKey[dict[str, dict[str, Any] | None]] = HassKey(
    "condition_description_cache"
)
CONDITION_PLATFORM_SUBSCRIPTIONS: HassKey[
    list[Callable[[set[str]], Coroutine[Any, Any, None]]]
] = HassKey("condition_platform_subscriptions")
CONDITIONS: HassKey[dict[str, str]] = HassKey("conditions")


# Basic schemas to sanity check the condition descriptions,
# full validation is done by hassfest.conditions
_FIELD_DESCRIPTION_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SELECTOR): selector.validate_selector,
    },
    extra=vol.ALLOW_EXTRA,
)

_CONDITION_DESCRIPTION_SCHEMA = vol.Schema(
    {
        vol.Optional("target"): TargetSelector.CONFIG_SCHEMA,
        vol.Optional("fields"): vol.Schema({str: _FIELD_DESCRIPTION_SCHEMA}),
    },
    extra=vol.ALLOW_EXTRA,
)


def starts_with_dot(key: str) -> str:
    """Check if key starts with dot."""
    if not key.startswith("."):
        raise vol.Invalid("Key does not start with .")
    return key


_CONDITIONS_DESCRIPTION_SCHEMA = vol.Schema(
    {
        vol.Remove(vol.All(str, starts_with_dot)): object,
        cv.underscore_slug: vol.Any(None, _CONDITION_DESCRIPTION_SCHEMA),
    }
)


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the condition helper."""
    hass.data[CONDITION_DESCRIPTION_CACHE] = {}
    hass.data[CONDITION_PLATFORM_SUBSCRIPTIONS] = []
    hass.data[CONDITIONS] = {}
    hass.data[_DATA_HISTORY_PRIMING_MANAGER] = _HistoryPrimingManager(hass)

    await async_process_integration_platforms(
        hass, "condition", _register_condition_platform, wait_for_platforms=True
    )


@callback
def async_subscribe_platform_events(
    hass: HomeAssistant,
    on_event: Callable[[set[str]], Coroutine[Any, Any, None]],
) -> Callable[[], None]:
    """Subscribe to condition platform events."""
    condition_platform_event_subscriptions = hass.data[CONDITION_PLATFORM_SUBSCRIPTIONS]

    def remove_subscription() -> None:
        condition_platform_event_subscriptions.remove(on_event)

    condition_platform_event_subscriptions.append(on_event)
    return remove_subscription


async def _register_condition_platform(
    hass: HomeAssistant, integration_domain: str, platform: ConditionProtocol
) -> None:
    """Register a condition platform and notify listeners.

    If the condition platform does not provide any conditions,
    listeners will not be notified.
    """
    new_conditions: set[str] = set()
    conditions = hass.data[CONDITIONS]

    if hasattr(platform, "async_get_conditions"):
        all_conditions = await platform.async_get_conditions(hass)
        for condition_key in all_conditions:
            condition_key = get_absolute_description_key(
                integration_domain, condition_key
            )
            if condition_key not in conditions:
                conditions[condition_key] = integration_domain
                new_conditions.add(condition_key)
        if not new_conditions:
            if not all_conditions:
                _LOGGER.debug(
                    "Integration %s returned no conditions in async_get_conditions",
                    integration_domain,
                )
            return
    else:
        _LOGGER.debug(
            "Integration %s does not provide condition support, skipping",
            integration_domain,
        )
        return

    # We don't use gather here because gather adds additional overhead
    # when wrapping each coroutine in a task, and we expect our listeners
    # to call condition.async_get_all_descriptions which will only yield
    # the first time it's called, after that it returns cached data.
    for listener in hass.data[CONDITION_PLATFORM_SUBSCRIPTIONS]:
        try:
            await listener(new_conditions)
        except Exception:
            _LOGGER.exception("Error while notifying condition platform listener")


_CONDITION_BASE_SCHEMA = vol.Schema(
    {
        **cv.CONDITION_BASE_SCHEMA,
        vol.Required(CONF_CONDITION): str,
    }
)
_CONDITION_SCHEMA = _CONDITION_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_OPTIONS): object,
        vol.Optional(CONF_TARGET): cv.TARGET_FIELDS,
    }
)


class ConditionChecker(abc.ABC):
    """Base class for condition checkers."""

    _set_up = False
    _unloaded = False

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize condition checker."""
        self._hass = hass

    def __call__(
        self, hass: HomeAssistant, variables: TemplateVarsType = None
    ) -> bool | None:
        """Check the condition.

        `hass` parameter is for backwards compatibility only and is always ignored.
        """
        return self.async_check(variables=variables)

    def __del__(self) -> None:
        """Clean up when the checker is deleted."""
        if self._unloaded:
            return
        try:
            self.async_unload()
        except Exception:
            _LOGGER.exception("Error while unloading condition checker")

    @final
    async def async_setup(self) -> None:
        """Set up the condition checker.

        Users of conditions do not need to call this method directly. It is called
        automatically by async_from_config and async_conditions_from_config.
        """
        await self._async_setup()
        self._set_up = True

    async def _async_setup(self) -> None:  # noqa: B027
        """Set up the condition checker.

        Intended to be overridden in derived classes that need to do setup.
        """

    @final
    def async_unload(self) -> None:
        """Clean up any resources held by the checker.

        Users of conditions must call this method when they are done with the
        checker to ensure resources are released.
        """
        self._async_unload()
        self._unloaded = True

    def _async_unload(self) -> None:  # noqa: B027
        """Clean up any resources held by the checker.

        Intended to be overridden in derived classes that need to do unloading.
        """

    @final
    def async_check(
        self, *, variables: TemplateVarsType = None, **kwargs: Never
    ) -> bool | None:
        """Check the condition."""
        if not self._set_up:
            raise HomeAssistantError("Condition checker is not set up")
        with trace_condition(variables):
            result = self._async_check(variables=variables)
            condition_trace_update_result(result=result)
            return result

    @abc.abstractmethod
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool | None:
        """Check the condition."""


class LegacyConditionChecker(ConditionChecker):
    """Condition checker wrapping a legacy condition factory function."""

    def __init__(self, hass: HomeAssistant, checker: ConditionCheckerType) -> None:
        """Initialize condition checker."""
        super().__init__(hass)
        self._checker = checker

    @override
    def _async_check(self, variables: TemplateVarsType = None, **kwargs: Any) -> bool:
        return self._checker(self._hass, variables)


class DisabledConditionChecker(ConditionChecker):
    """Condition checker for disabled conditions."""

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> None:
        return None


class CompoundConditionChecker(ConditionChecker):
    """Base class for compound condition checkers (and/or/not)."""

    def __init__(self, hass: HomeAssistant, conditions: list[ConditionChecker]) -> None:
        """Initialize condition checker."""
        super().__init__(hass)
        self._conditions = conditions

    @override
    def _async_unload(self) -> None:
        """Clean up child conditions."""
        for condition in self._conditions:
            condition.async_unload()


class Condition(ConditionChecker):
    """Condition class."""

    @classmethod
    async def async_validate_complete_config(
        cls, hass: HomeAssistant, complete_config: ConfigType
    ) -> ConfigType:
        """Validate complete config.

        The complete config includes fields that are generic to all conditions,
        such as the alias.
        This method should be overridden by conditions that need to migrate
        from the old-style config.
        """
        complete_config = _CONDITION_SCHEMA(complete_config)

        specific_config: ConfigType = {}
        for key in (CONF_OPTIONS, CONF_TARGET):
            if key in complete_config:
                specific_config[key] = complete_config.pop(key)
        specific_config = await cls.async_validate_config(hass, specific_config)

        for key in (CONF_OPTIONS, CONF_TARGET):
            if key in specific_config:
                complete_config[key] = specific_config[key]

        return complete_config

    @classmethod
    @abc.abstractmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        super().__init__(hass)


ATTR_BEHAVIOR: Final = "behavior"
BEHAVIOR_ANY: Final = "any"
BEHAVIOR_ALL: Final = "all"

ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL = vol.Schema(
    {
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
        vol.Required(CONF_OPTIONS, default={}): {
            vol.Required(ATTR_BEHAVIOR, default=BEHAVIOR_ANY): vol.In(
                [BEHAVIOR_ANY, BEHAVIOR_ALL]
            ),
            vol.Optional(CONF_FOR): cv.positive_time_period,
        },
    }
)


_DATA_HISTORY_PRIMING_MANAGER: HassKey[_HistoryPrimingManager] = HassKey(
    "condition_history_priming_manager"
)


class _HistoryPrimingManager:
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


class EntityConditionBase(Condition):
    """Base class for entity conditions."""

    _domain_specs: Mapping[str, DomainSpec]
    _excluded_states: Final[frozenset[str]] = frozenset(
        {STATE_UNAVAILABLE, STATE_UNKNOWN}
    )
    _schema: vol.Schema = ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL
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

        manager = self._hass.data[_DATA_HISTORY_PRIMING_MANAGER]
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
        vol.Required(CONF_OPTIONS): {
            vol.Required("threshold"): NumericThresholdSelector(
                NumericThresholdSelectorConfig(mode=NumericThresholdMode.IS)
            ),
        },
    }
)


class EntityNumericalConditionBase(EntityConditionBase):
    """Condition for numerical state comparisons with above/below thresholds."""

    _schema = NUMERICAL_CONDITION_SCHEMA
    _valid_unit: str | None | UndefinedType = UNDEFINED

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
    valid_unit: str | None | UndefinedType = UNDEFINED,
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
) -> vol.Schema:
    """Factory for numerical condition schema with unit option."""
    return ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL.extend(
        {
            vol.Required(CONF_OPTIONS): {
                vol.Required("threshold"): NumericThresholdSelector(
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


class ConditionProtocol(Protocol):
    """Define the format of condition modules."""

    async def async_get_conditions(
        self, hass: HomeAssistant
    ) -> dict[str, type[Condition]]:
        """Return the conditions provided by this integration."""


@dataclass(slots=True)
class ConditionConfig:
    """Condition config."""

    options: dict[str, Any] | None = None
    target: dict[str, Any] | None = None


class ConditionCheckParams(TypedDict, total=False):
    """Condition check params."""

    variables: TemplateVarsType


type ConditionCheckerType = Callable[[HomeAssistant, TemplateVarsType], bool]
type ConditionCheckerTypeOptional = Callable[
    [HomeAssistant, TemplateVarsType], bool | None
]


def condition_trace_append(variables: TemplateVarsType, path: str) -> TraceElement:
    """Append a TraceElement to trace[path]."""
    trace_element = TraceElement(variables, path)
    trace_append_element(trace_element)
    return trace_element


def condition_trace_set_result(result: bool, **kwargs: Any) -> None:
    """Set the result of TraceElement at the top of the stack."""
    node = trace_stack_top(trace_stack_cv)

    # The condition function may be called directly, in which case tracing
    # is not setup
    if not node:
        return

    node.set_result(result=result, **kwargs)


def condition_trace_update_result(**kwargs: Any) -> None:
    """Update the result of TraceElement at the top of the stack."""
    node = trace_stack_top(trace_stack_cv)

    # The condition function may be called directly, in which case tracing
    # is not setup
    if not node:
        return

    node.update_result(**kwargs)


class trace_condition:
    """Trace condition evaluation."""

    __slots__ = ("_should_pop", "_trace_element", "_variables")

    _should_pop: bool
    _trace_element: TraceElement

    def __init__(self, variables: TemplateVarsType) -> None:
        """Store the variables for the trace element."""
        self._variables = variables

    def __enter__(self) -> TraceElement:
        """Start tracing the condition evaluation."""
        should_pop = True
        trace_element = trace_stack_top(trace_stack_cv)
        if trace_element and trace_element.reuse_by_child:
            should_pop = False
            trace_element.reuse_by_child = False
        else:
            trace_element = condition_trace_append(self._variables, trace_path_get())
            trace_stack_push(trace_stack_cv, trace_element)
        self._should_pop = should_pop
        self._trace_element = trace_element
        return trace_element

    def __exit__(
        self, exc_type: object, exc_val: BaseException | None, exc_tb: object
    ) -> None:
        """Finish tracing the condition evaluation."""
        try:
            if exc_val is not None and isinstance(exc_val, Exception):
                self._trace_element.set_error(exc_val)
        finally:
            if self._should_pop:
                trace_stack_pop(trace_stack_cv)


@overload
def trace_condition_function(
    condition: ConditionCheckerType,
) -> ConditionCheckerType: ...


@overload
def trace_condition_function(
    condition: ConditionCheckerTypeOptional,
) -> ConditionCheckerTypeOptional: ...


def trace_condition_function(
    condition: ConditionCheckerType | ConditionCheckerTypeOptional,
) -> ConditionCheckerType | ConditionCheckerTypeOptional:
    """Wrap a condition function to enable basic tracing."""

    @ft.wraps(condition)
    def wrapper(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool | None:
        """Trace condition."""
        with trace_condition(variables):
            result = condition(hass, variables)
            condition_trace_update_result(result=result)
            return result

    return wrapper


async def _async_get_condition_platform(
    hass: HomeAssistant, condition_key: str
) -> tuple[str, ConditionProtocol | None]:
    platform_and_sub_type = condition_key.split(".")
    platform: str | None = platform_and_sub_type[0]
    platform = _PLATFORM_ALIASES.get(platform, platform)
    if platform is None:
        return "", None

    try:
        integration = await async_get_integration(hass, platform)
    except IntegrationNotFound:
        raise HomeAssistantError(
            f'Invalid condition "{condition_key}" specified'
        ) from None
    try:
        platform_module = await integration.async_get_platform("condition")
    except ImportError:
        raise HomeAssistantError(
            f"Integration '{platform}' does not provide condition support"
        ) from None

    # Ensure conditions are registered so descriptions can be loaded
    await _register_condition_platform(hass, platform, platform_module)

    return platform, platform_module


async def async_from_config(
    hass: HomeAssistant,
    config: ConfigType,
) -> ConditionChecker:
    """Turn a condition configuration into a method.

    Should be run on the event loop.
    """
    # Check if condition is not enabled
    if CONF_ENABLED in config:
        enabled = config[CONF_ENABLED]
        if isinstance(enabled, Template):
            try:
                enabled = enabled.async_render(limited=True)
            except TemplateError as err:
                raise HomeAssistantError(
                    f"Error rendering condition enabled template: {err}"
                ) from err
        if not enabled:
            disabled_checker = DisabledConditionChecker(hass)
            await disabled_checker.async_setup()
            return disabled_checker

    condition_key: str = config[CONF_CONDITION]
    factory: Any = None
    platform_domain, platform = await _async_get_condition_platform(hass, condition_key)

    if platform is not None:
        condition_descriptors = await platform.async_get_conditions(hass)
        relative_condition_key = get_relative_description_key(
            platform_domain, condition_key
        )
        condition_cls = condition_descriptors[relative_condition_key]
        condition = condition_cls(
            hass,
            ConditionConfig(
                options=config.get(CONF_OPTIONS),
                target=config.get(CONF_TARGET),
            ),
        )
        await condition.async_setup()
        return condition

    for fmt in (ASYNC_FROM_CONFIG_FORMAT, FROM_CONFIG_FORMAT):
        factory = getattr(sys.modules[__name__], fmt.format(condition_key), None)

        if factory:
            break

    # Check for partials to properly determine if coroutine function
    check_factory = factory
    while isinstance(check_factory, ft.partial):
        check_factory = check_factory.func

    checker: ConditionChecker | ConditionCheckerType
    if inspect.iscoroutinefunction(check_factory):
        checker = await factory(hass, config)
    else:
        checker = factory(config)
    if not isinstance(checker, ConditionChecker):
        checker = LegacyConditionChecker(hass, checker)
    await checker.async_setup()
    return checker


async def async_and_from_config(
    hass: HomeAssistant, config: ConfigType
) -> ConditionChecker:
    """Create multi condition matcher using 'AND'."""
    checks = [await async_from_config(hass, entry) for entry in config["conditions"]]
    return AndConditionChecker(hass, checks)


class AndConditionChecker(CompoundConditionChecker):
    """Condition checker for 'and' compound conditions."""

    @callback
    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Test and condition."""
        errors = []
        for index, condition in enumerate(self._conditions):
            try:
                with trace_path(["conditions", str(index)]):
                    if condition.async_check(**kwargs) is False:
                        return False
            except ConditionError as ex:
                errors.append(
                    ConditionErrorIndex(
                        "and", index=index, total=len(self._conditions), error=ex
                    )
                )

        # Raise the errors if no check was false
        if errors:
            raise ConditionErrorContainer("and", errors=errors)

        return True


async def async_or_from_config(
    hass: HomeAssistant, config: ConfigType
) -> ConditionChecker:
    """Create multi condition matcher using 'OR'."""
    checks = [await async_from_config(hass, entry) for entry in config["conditions"]]
    return OrConditionChecker(hass, checks)


class OrConditionChecker(CompoundConditionChecker):
    """Condition checker for 'or' compound conditions."""

    @callback
    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Test or condition."""
        errors = []
        for index, condition in enumerate(self._conditions):
            try:
                with trace_path(["conditions", str(index)]):
                    if condition.async_check(**kwargs) is True:
                        return True
            except ConditionError as ex:
                errors.append(
                    ConditionErrorIndex(
                        "or", index=index, total=len(self._conditions), error=ex
                    )
                )

        # Raise the errors if no check was true
        if errors:
            raise ConditionErrorContainer("or", errors=errors)

        return False


async def async_not_from_config(
    hass: HomeAssistant, config: ConfigType
) -> ConditionChecker:
    """Create multi condition matcher using 'NOT'."""
    checks = [await async_from_config(hass, entry) for entry in config["conditions"]]
    return NotConditionChecker(hass, checks)


class NotConditionChecker(CompoundConditionChecker):
    """Condition checker for 'not' compound conditions."""

    @callback
    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Test not condition."""
        errors = []
        for index, condition in enumerate(self._conditions):
            try:
                with trace_path(["conditions", str(index)]):
                    if condition.async_check(**kwargs):
                        return False
            except ConditionError as ex:
                errors.append(
                    ConditionErrorIndex(
                        "not", index=index, total=len(self._conditions), error=ex
                    )
                )

        # Raise the errors if no check was true
        if errors:
            raise ConditionErrorContainer("not", errors=errors)

        return True


def numeric_state(
    hass: HomeAssistant,
    entity: str | State | None,
    below: float | str | None = None,
    above: float | str | None = None,
    value_template: Template | None = None,
    variables: TemplateVarsType = None,
) -> bool:
    """Test a numeric state condition."""
    return run_callback_threadsafe(
        hass.loop,
        async_numeric_state,
        hass,
        entity,
        below,
        above,
        value_template,
        variables,
    ).result()


def async_numeric_state(
    hass: HomeAssistant,
    entity: str | State | None,
    below: float | str | None = None,
    above: float | str | None = None,
    value_template: Template | None = None,
    variables: TemplateVarsType = None,
    attribute: str | None = None,
) -> bool:
    """Test a numeric state condition."""
    if entity is None:
        raise ConditionErrorMessage("numeric_state", "no entity specified")

    if isinstance(entity, str):
        entity_id = entity

        if (entity := hass.states.get(entity)) is None:
            raise ConditionErrorMessage("numeric_state", f"unknown entity {entity_id}")
    else:
        entity_id = entity.entity_id

    if attribute is not None and attribute not in entity.attributes:
        condition_trace_set_result(
            False,
            message=f"attribute '{attribute}' of entity {entity_id} does not exist",
        )
        return False

    value: Any = None
    if value_template is None:
        if attribute is None:
            value = entity.state
        else:
            value = entity.attributes.get(attribute)
    else:
        variables = dict(variables or {})
        variables["state"] = entity
        try:
            value = value_template.async_render(variables)
        except TemplateError as ex:
            raise ConditionErrorMessage(
                "numeric_state", f"template error: {ex}"
            ) from ex

    # Known states or attribute values that never match the numeric condition
    if value in (None, STATE_UNAVAILABLE, STATE_UNKNOWN):
        condition_trace_set_result(
            False,
            message=f"value '{value}' is non-numeric and treated as False",
        )
        return False

    try:
        fvalue = float(value)
    except (ValueError, TypeError) as ex:
        raise ConditionErrorMessage(
            "numeric_state",
            f"entity {entity_id} state '{value}' cannot be processed as a number",
        ) from ex

    if below is not None:
        if isinstance(below, str):
            if not (below_entity := hass.states.get(below)):
                raise ConditionErrorMessage(
                    "numeric_state", f"unknown 'below' entity {below}"
                )
            if below_entity.state in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                return False
            try:
                if fvalue >= float(below_entity.state):
                    condition_trace_set_result(
                        False,
                        state=fvalue,
                        wanted_state_below=float(below_entity.state),
                    )
                    return False
            except (ValueError, TypeError) as ex:
                raise ConditionErrorMessage(
                    "numeric_state",
                    (
                        f"the 'below' entity {below} state '{below_entity.state}'"
                        " cannot be processed as a number"
                    ),
                ) from ex
        elif fvalue >= below:
            condition_trace_set_result(False, state=fvalue, wanted_state_below=below)
            return False

    if above is not None:
        if isinstance(above, str):
            if not (above_entity := hass.states.get(above)):
                raise ConditionErrorMessage(
                    "numeric_state", f"unknown 'above' entity {above}"
                )
            if above_entity.state in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                return False
            try:
                if fvalue <= float(above_entity.state):
                    condition_trace_set_result(
                        False,
                        state=fvalue,
                        wanted_state_above=float(above_entity.state),
                    )
                    return False
            except (ValueError, TypeError) as ex:
                raise ConditionErrorMessage(
                    "numeric_state",
                    (
                        f"the 'above' entity {above} state '{above_entity.state}'"
                        " cannot be processed as a number"
                    ),
                ) from ex
        elif fvalue <= above:
            condition_trace_set_result(False, state=fvalue, wanted_state_above=above)
            return False

    condition_trace_set_result(True, state=fvalue)
    return True


def async_numeric_state_from_config(config: ConfigType) -> ConditionCheckerType:
    """Wrap action method with state based condition."""
    entity_ids = config.get(CONF_ENTITY_ID, [])
    attribute = config.get(CONF_ATTRIBUTE)
    below = config.get(CONF_BELOW)
    above = config.get(CONF_ABOVE)
    value_template = config.get(CONF_VALUE_TEMPLATE)

    def if_numeric_state(
        hass: HomeAssistant, variables: TemplateVarsType = None
    ) -> bool:
        """Test numeric state condition."""
        errors = []
        for index, entity_id in enumerate(entity_ids):
            try:
                with trace_path(["entity_id", str(index)]), trace_condition(variables):
                    if not async_numeric_state(
                        hass,
                        entity_id,
                        below,
                        above,
                        value_template,
                        variables,
                        attribute,
                    ):
                        return False
            except ConditionError as ex:
                errors.append(
                    ConditionErrorIndex(
                        "numeric_state", index=index, total=len(entity_ids), error=ex
                    )
                )

        # Raise the errors if no check was false
        if errors:
            raise ConditionErrorContainer("numeric_state", errors=errors)

        return True

    return if_numeric_state


def state(
    hass: HomeAssistant,
    entity: str | State | None,
    req_state: Any,
    for_period: timedelta | None = None,
    attribute: str | None = None,
    variables: TemplateVarsType = None,
) -> bool:
    """Test if state matches requirements.

    Async friendly.
    """
    if entity is None:
        raise ConditionErrorMessage("state", "no entity specified")

    if isinstance(entity, str):
        entity_id = entity

        if (entity := hass.states.get(entity)) is None:
            raise ConditionErrorMessage("state", f"unknown entity {entity_id}")
    else:
        entity_id = entity.entity_id

    if attribute is not None and attribute not in entity.attributes:
        condition_trace_set_result(
            False,
            message=f"attribute '{attribute}' of entity {entity_id} does not exist",
        )
        return False

    assert isinstance(entity, State)

    if attribute is None:
        value: Any = entity.state
    else:
        value = entity.attributes.get(attribute)

    if not isinstance(req_state, list):
        req_state = [req_state]

    is_state = False
    for req_state_value in req_state:
        state_value = req_state_value
        if (
            isinstance(req_state_value, str)
            and INPUT_ENTITY_ID.match(req_state_value) is not None
        ):
            if not (state_entity := hass.states.get(req_state_value)):
                raise ConditionErrorMessage(
                    "state", f"the 'state' entity {req_state_value} is unavailable"
                )
            state_value = state_entity.state
        is_state = value == state_value
        if is_state:
            break

    if for_period is None or not is_state:
        condition_trace_set_result(is_state, state=value, wanted_state=state_value)
        return is_state

    try:
        for_period = cv.positive_time_period(render_complex(for_period, variables))
    except TemplateError as ex:
        raise ConditionErrorMessage("state", f"template error: {ex}") from ex
    except vol.Invalid as ex:
        raise ConditionErrorMessage("state", f"schema error: {ex}") from ex

    duration = dt_util.utcnow() - cast(timedelta, for_period)
    duration_ok = duration > entity.last_changed
    condition_trace_set_result(duration_ok, state=value, duration=duration)
    return duration_ok


def state_from_config(config: ConfigType) -> ConditionCheckerType:
    """Wrap action method with state based condition."""
    entity_ids = config.get(CONF_ENTITY_ID, [])
    req_states: str | list[str] = config.get(CONF_STATE, [])
    for_period = config.get(CONF_FOR)
    attribute = config.get(CONF_ATTRIBUTE)
    match = config.get(CONF_MATCH, ENTITY_MATCH_ALL)

    if not isinstance(req_states, list):
        req_states = [req_states]

    def if_state(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        """Test if condition."""
        errors = []
        result: bool = match != ENTITY_MATCH_ANY
        for index, entity_id in enumerate(entity_ids):
            try:
                with trace_path(["entity_id", str(index)]), trace_condition(variables):
                    if state(
                        hass, entity_id, req_states, for_period, attribute, variables
                    ):
                        result = True
                    elif match == ENTITY_MATCH_ALL:
                        return False
            except ConditionError as ex:
                errors.append(
                    ConditionErrorIndex(
                        "state", index=index, total=len(entity_ids), error=ex
                    )
                )

        # Raise the errors if no check was false
        if errors:
            raise ConditionErrorContainer("state", errors=errors)

        return result

    return if_state


def template(
    hass: HomeAssistant, value_template: Template, variables: TemplateVarsType = None
) -> bool:
    """Test if template condition matches."""
    return run_callback_threadsafe(
        hass.loop, async_template, hass, value_template, variables
    ).result()


def async_template(
    hass: HomeAssistant,
    value_template: Template,
    variables: TemplateVarsType = None,
    trace_result: bool = True,
) -> bool:
    """Test if template condition matches."""
    try:
        info = value_template.async_render_to_info(variables, parse_result=False)
        value = info.result()
    except TemplateError as ex:
        raise ConditionErrorMessage("template", str(ex)) from ex

    result = value.lower() == "true"
    if trace_result:
        condition_trace_set_result(result, entities=list(info.entities))
    return result


def async_template_from_config(config: ConfigType) -> ConditionCheckerType:
    """Wrap action method with state based condition."""
    value_template = cast(Template, config.get(CONF_VALUE_TEMPLATE))

    def template_if(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        """Validate template based if-condition."""
        return async_template(hass, value_template, variables)

    return template_if


def time(
    hass: HomeAssistant,
    before: dt_time | str | None = None,
    after: dt_time | str | None = None,
    weekday: str | Container[str] | None = None,
) -> bool:
    """Test if local time condition matches.

    Handle the fact that time is continuous and we may be testing for
    a period that crosses midnight. In that case it is easier to test
    for the opposite. "(23:59 <= now < 00:01)" would be the same as
    "not (00:01 <= now < 23:59)".
    """
    from homeassistant.components.sensor import SensorDeviceClass  # noqa: PLC0415

    now = dt_util.now()
    now_time = now.time()

    if after is None:
        after = dt_time(0)
    elif isinstance(after, str):
        if not (after_entity := hass.states.get(after)):
            raise ConditionErrorMessage("time", f"unknown 'after' entity {after}")
        if after_entity.domain == "input_datetime":
            after = dt_time(
                after_entity.attributes.get("hour", 23),
                after_entity.attributes.get("minute", 59),
                after_entity.attributes.get("second", 59),
            )
        elif after_entity.domain == "time" and after_entity.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            after = datetime.strptime(after_entity.state, "%H:%M:%S").time()
        elif (
            after_entity.attributes.get(EntityStateAttribute.DEVICE_CLASS)
            in (SensorDeviceClass.TIMESTAMP, SensorDeviceClass.UPTIME)
        ) and after_entity.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            after_datetime = dt_util.parse_datetime(after_entity.state)
            if after_datetime is None:
                return False
            after = dt_util.as_local(after_datetime).time()
        else:
            return False

    if before is None:
        before = dt_time(23, 59, 59, 999999)
    elif isinstance(before, str):
        if not (before_entity := hass.states.get(before)):
            raise ConditionErrorMessage("time", f"unknown 'before' entity {before}")
        if before_entity.domain == "input_datetime":
            before = dt_time(
                before_entity.attributes.get("hour", 23),
                before_entity.attributes.get("minute", 59),
                before_entity.attributes.get("second", 59),
            )
        elif before_entity.domain == "time":
            try:
                before = datetime.strptime(before_entity.state, "%H:%M:%S").time()
            except ValueError:
                return False
        elif (
            before_entity.attributes.get(EntityStateAttribute.DEVICE_CLASS)
            in (SensorDeviceClass.TIMESTAMP, SensorDeviceClass.UPTIME)
        ) and before_entity.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            before_timedatime = dt_util.parse_datetime(before_entity.state)
            if before_timedatime is None:
                return False
            before = dt_util.as_local(before_timedatime).time()
        else:
            return False

    if after < before:
        condition_trace_update_result(after=after, now_time=now_time, before=before)
        if not after <= now_time < before:
            return False
    else:
        condition_trace_update_result(after=after, now_time=now_time, before=before)
        if before <= now_time < after:
            return False

    if weekday is not None:
        now_weekday = WEEKDAYS[now.weekday()]

        condition_trace_update_result(weekday=weekday, now_weekday=now_weekday)
        if (
            isinstance(weekday, str) and weekday != now_weekday
        ) or now_weekday not in weekday:
            return False

    return True


def time_from_config(config: ConfigType) -> ConditionCheckerType:
    """Wrap action method with time based condition."""
    before = config.get(CONF_BEFORE)
    after = config.get(CONF_AFTER)
    weekday = config.get(CONF_WEEKDAY)

    def time_if(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        """Validate time based if-condition."""
        return time(hass, before, after, weekday)

    return time_if


async def async_trigger_from_config(
    hass: HomeAssistant, config: ConfigType
) -> ConditionCheckerType:
    """Test a trigger condition."""
    trigger_id = config[CONF_ID]

    def trigger_if(hass: HomeAssistant, variables: TemplateVarsType = None) -> bool:
        """Validate trigger based if-condition."""
        return (
            variables is not None
            and "trigger" in variables
            and variables["trigger"].get("id") in trigger_id
        )

    return trigger_if


def numeric_state_validate_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate numeric_state condition config."""

    registry = er.async_get(hass)
    config = dict(config)
    config[CONF_ENTITY_ID] = er.async_validate_entity_ids(
        registry, cv.entity_ids_or_uuids(config[CONF_ENTITY_ID])
    )
    return config


def state_validate_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate state condition config."""

    registry = er.async_get(hass)
    config = dict(config)
    config[CONF_ENTITY_ID] = er.async_validate_entity_ids(
        registry, cv.entity_ids_or_uuids(config[CONF_ENTITY_ID])
    )
    return config


async def async_validate_condition_config(
    hass: HomeAssistant, config: ConfigType | str
) -> ConfigType:
    """Validate config."""
    if isinstance(config, str):
        config = {
            CONF_CONDITION: "template",
            CONF_VALUE_TEMPLATE: cv.dynamic_template(config),
        }
    condition_key: str = config[CONF_CONDITION]

    if condition_key in ("and", "not", "or"):
        conditions = []
        for sub_cond in config["conditions"]:
            sub_cond = await async_validate_condition_config(hass, sub_cond)
            conditions.append(sub_cond)
        config["conditions"] = conditions
        return config

    platform_domain, platform = await _async_get_condition_platform(hass, condition_key)

    if platform is not None:
        condition_descriptors = await platform.async_get_conditions(hass)
        relative_condition_key = get_relative_description_key(
            platform_domain, condition_key
        )
        if not (condition_class := condition_descriptors.get(relative_condition_key)):
            raise vol.Invalid(f"Invalid condition '{condition_key}' specified")
        return await condition_class.async_validate_complete_config(hass, config)

    config = move_options_fields_to_top_level(config, _CONDITION_BASE_SCHEMA)

    if condition_key in ("numeric_state", "state"):
        validator = cast(
            Callable[[HomeAssistant, ConfigType], ConfigType],
            getattr(
                sys.modules[__name__], VALIDATE_CONFIG_FORMAT.format(condition_key)
            ),
        )
        return validator(hass, config)

    return config


async def async_validate_conditions_config(
    hass: HomeAssistant, conditions: list[ConfigType]
) -> list[ConfigType | Template]:
    """Validate config."""
    # No gather here because async_validate_condition_config is unlikely
    # to suspend and the overhead of creating many tasks is not worth it
    return [await async_validate_condition_config(hass, cond) for cond in conditions]


async def async_conditions_from_config(
    hass: HomeAssistant,
    condition_configs: list[ConfigType],
    logger: logging.Logger,
    name: str,
) -> ConditionsChecker:
    """AND all conditions."""
    checks = [
        await async_from_config(hass, condition_config)
        for condition_config in condition_configs
    ]
    return ConditionsChecker(checks, logger, name)


class ConditionsChecker:
    """Condition checker that ANDs multiple conditions.

    Used by automations and template entities. Unlike AndConditionChecker,
    this logs warnings on errors instead of raising, and uses "condition"
    as the trace path prefix.
    """

    def __init__(
        self,
        conditions: list[ConditionChecker],
        logger: logging.Logger,
        name: str,
    ) -> None:
        """Initialize condition checker."""
        self._conditions = conditions
        self._logger = logger
        self._name = name
        self._unloaded = False

    def __call__(self, variables: TemplateVarsType = None) -> bool:
        """Check all conditions."""
        return self.async_check(variables=variables)

    def __del__(self) -> None:
        """Clean up when the checker is deleted."""
        if self._unloaded:
            return
        try:
            self.async_unload()
        except Exception:
            _LOGGER.exception("Error while unloading condition checker")

    def async_unload(self) -> None:
        """Clean up child conditions."""
        self._unloaded = True
        for condition in self._conditions:
            condition.async_unload()

    def async_check(
        self, *, variables: TemplateVarsType = None, **kwargs: Never
    ) -> bool:
        """AND all conditions."""
        errors: list[ConditionErrorIndex] = []
        for index, condition in enumerate(self._conditions):
            try:
                with trace_path(["condition", str(index)]):
                    if condition.async_check(variables=variables, **kwargs) is False:
                        return False
            except ConditionError as ex:
                errors.append(
                    ConditionErrorIndex(
                        "condition", index=index, total=len(self._conditions), error=ex
                    )
                )

        if errors:
            self._logger.warning(
                "Error evaluating condition in '%s':\n%s",
                self._name,
                ConditionErrorContainer("condition", errors=errors),
            )
            return False

        return True


@callback
def async_extract_entities(config: ConfigType | Template) -> set[str]:
    """Extract entities from a condition."""
    referenced: set[str] = set()
    to_process = deque([config])

    while to_process:
        config = to_process.popleft()
        if isinstance(config, Template):
            continue

        condition = config[CONF_CONDITION]

        if condition in ("and", "not", "or"):
            to_process.extend(config["conditions"])
            continue

        if condition == "time":
            # The before and after options can be a time or an entity id.
            for key in (CONF_AFTER, CONF_BEFORE):
                if isinstance(value := config.get(key), str) and valid_entity_id(value):
                    referenced.add(value)
            continue

        if condition == "zone":
            options = config.get(CONF_OPTIONS, {})
            referenced.update(options.get(CONF_ENTITY_ID, []))
            referenced.update(options.get(CONF_ZONE, []))

        elif condition in (
            "zone.in_zone",
            "zone.not_in_zone",
            "zone.occupancy_is_detected",
            "zone.occupancy_is_not_detected",
        ):
            if zone_entity_id := config.get(CONF_OPTIONS, {}).get(CONF_ZONE):
                referenced.add(zone_entity_id)

        entity_ids = config.get(CONF_ENTITY_ID)

        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]

        if entity_ids is not None:
            referenced.update(entity_ids)

        if target_entities := _get_targets_from_condition_config(
            config, CONF_ENTITY_ID
        ):
            referenced.update(target_entities)

    return referenced


@callback
def async_extract_devices(config: ConfigType | Template) -> set[str]:
    """Extract devices from a condition."""
    referenced: set[str] = set()
    to_process = deque([config])

    while to_process:
        config = to_process.popleft()
        if isinstance(config, Template):
            continue

        condition = config[CONF_CONDITION]

        if condition in ("and", "not", "or"):
            to_process.extend(config["conditions"])
            continue

        if condition == "device":
            if (device_id := config.get(CONF_DEVICE_ID)) is not None:
                referenced.add(device_id)
            continue

        if target_devices := _get_targets_from_condition_config(config, CONF_DEVICE_ID):
            referenced.update(target_devices)

    return referenced


@callback
def async_extract_targets(
    config: ConfigType | Template,
    target_type: Literal["area_id", "floor_id", "label_id"],
) -> set[str]:
    """Extract targets from a condition."""
    referenced: set[str] = set()
    to_process = deque([config])

    while to_process:
        config = to_process.popleft()
        if isinstance(config, Template):
            continue

        condition = config[CONF_CONDITION]

        if condition in ("and", "not", "or"):
            to_process.extend(config["conditions"])
            continue

        if targets := _get_targets_from_condition_config(config, target_type):
            referenced.update(targets)

    return referenced


@callback
def _get_targets_from_condition_config(
    config: ConfigType,
    target: Literal["entity_id", "device_id", "area_id", "floor_id", "label_id"],
) -> list[str]:
    """Extract targets from a condition target config."""
    if not (target_conf := config.get(CONF_TARGET)):
        return []
    if not (targets := target_conf.get(target)):
        return []

    return [targets] if isinstance(targets, str) else targets


def _load_conditions_file(integration: Integration) -> dict[str, Any]:
    """Load conditions file for an integration."""
    try:
        return cast(
            dict[str, Any],
            _CONDITIONS_DESCRIPTION_SCHEMA(
                load_yaml_dict(str(integration.file_path / "conditions.yaml"))
            ),
        )
    except FileNotFoundError:
        _LOGGER.warning(
            "Unable to find conditions.yaml for the %s integration", integration.domain
        )
        return {}
    except (HomeAssistantError, vol.Invalid) as ex:
        _LOGGER.warning(
            "Unable to parse conditions.yaml for the %s integration: %s",
            integration.domain,
            ex,
        )
        return {}


def _load_conditions_files(
    integrations: Iterable[Integration],
) -> dict[str, dict[str, Any]]:
    """Load condition files for multiple integrations."""
    return {
        integration.domain: {
            get_absolute_description_key(integration.domain, key): value
            for key, value in _load_conditions_file(integration).items()
        }
        for integration in integrations
    }


async def async_get_all_descriptions(
    hass: HomeAssistant,
) -> dict[str, dict[str, Any] | None]:
    """Return descriptions (i.e. user documentation) for all conditions."""
    descriptions_cache = hass.data[CONDITION_DESCRIPTION_CACHE]

    conditions = hass.data[CONDITIONS]
    # See if there are new conditions not seen before.
    # Any condition that we saw before already has an entry in description_cache.
    all_conditions = set(conditions)
    previous_all_conditions = set(descriptions_cache)
    # If the conditions are the same, we can return the cache
    if previous_all_conditions == all_conditions:
        return descriptions_cache

    # Files we loaded for missing descriptions
    new_conditions_descriptions: dict[str, dict[str, Any]] = {}
    # We try to avoid making a copy in the event the cache is good,
    # but now we must make a copy in case new conditions get added
    # while we are loading the missing ones so we do not
    # add the new ones to the cache without their descriptions
    conditions = conditions.copy()

    if missing_conditions := all_conditions.difference(descriptions_cache):
        domains_with_missing_conditions = {
            conditions[missing_condition] for missing_condition in missing_conditions
        }
        ints_or_excs = await async_get_integrations(
            hass, domains_with_missing_conditions
        )
        integrations: list[Integration] = []
        for domain, int_or_exc in ints_or_excs.items():
            if type(int_or_exc) is Integration and int_or_exc.has_conditions:
                integrations.append(int_or_exc)
                continue
            if TYPE_CHECKING:
                assert isinstance(int_or_exc, Exception)
            _LOGGER.debug(
                "Failed to load conditions.yaml for integration: %s",
                domain,
                exc_info=int_or_exc,
            )

        if integrations:
            new_conditions_descriptions = await hass.async_add_executor_job(
                _load_conditions_files, integrations
            )

    # Make a copy of the old cache and add missing descriptions to it
    new_descriptions_cache = descriptions_cache.copy()
    for missing_condition in missing_conditions:
        domain = conditions[missing_condition]
        if (
            yaml_description := new_conditions_descriptions.get(domain, {}).get(
                missing_condition
            )
        ) is None:
            _LOGGER.debug(
                "No condition descriptions found for condition %s, skipping",
                missing_condition,
            )
            new_descriptions_cache[missing_condition] = None
            continue

        description = {"fields": yaml_description.get("fields", {})}
        if (target := yaml_description.get("target")) is not None:
            description["target"] = target

        new_descriptions_cache[missing_condition] = description

    hass.data[CONDITION_DESCRIPTION_CACHE] = new_descriptions_cache
    return new_descriptions_cache
