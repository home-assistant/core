"""Entity state trigger helpers."""

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, ClassVar, Final, Protocol, cast, override

import probatio

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_FOR,
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityStateAttribute,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    DOMAIN as HOMEASSISTANT_DOMAIN,
    HomeAssistant,
    State,
    async_get_hass_or_none,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import (
    DomainSpec,
    ThresholdConfig,
    filter_by_domain_specs,
)
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.selector import (
    NumericThresholdMode,
    NumericThresholdSelector,
    NumericThresholdSelectorConfig,
    NumericThresholdType,
)
from homeassistant.helpers.target import (
    TargetStateChangedData,
    async_track_target_selector_state_change_event,
)
from homeassistant.helpers.typing import UNDEFINED, ConfigType, UndefinedType
from homeassistant.util.unit_conversion import BaseUnitConverter

from .models import (
    NotTriggeredInfo,
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)

ATTR_BEHAVIOR: Final = "behavior"
BEHAVIOR_FIRST: Final = "first"
BEHAVIOR_ALL: Final = "all"
BEHAVIOR_EACH: Final = "each"


def _create_deprecated_behavior_issue(deprecated: str, replacement: str) -> None:
    """Inform the user a renamed trigger behavior value is still in use."""
    # Returns None when called from the wrong thread or before hass is set up
    # (e.g. a `check_config` run), in which case there's nothing to report to.
    if (hass := async_get_hass_or_none()) is None:
        return

    from homeassistant.helpers.issue_registry import (  # noqa: PLC0415
        IssueSeverity,
        async_create_issue,
    )

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_trigger_behavior_{deprecated}",
        breaks_in_ha_version="2027.1",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_trigger_behavior",
        translation_placeholders={
            "deprecated_behavior": deprecated,
            "new_behavior": replacement,
        },
    )


def _backwards_compatible_behavior(value: Any) -> Any:
    """Convert legacy behavior values to new ones."""
    if value == "any":
        _create_deprecated_behavior_issue("any", BEHAVIOR_EACH)
        return BEHAVIOR_EACH
    if value == "last":
        _create_deprecated_behavior_issue("last", BEHAVIOR_ALL)
        return BEHAVIOR_ALL
    return value


ENTITY_STATE_TRIGGER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_TARGET): cv.TARGET_FIELDS,
        probatio.Required(CONF_OPTIONS, default={}): {},
    }
)

ENTITY_STATE_TRIGGER_SCHEMA_WITH_BEHAVIOR = ENTITY_STATE_TRIGGER_SCHEMA.extend(
    {
        probatio.Required(CONF_OPTIONS, default={}): {
            probatio.Required(ATTR_BEHAVIOR, default=BEHAVIOR_EACH): probatio.All(
                _backwards_compatible_behavior,
                probatio.In([BEHAVIOR_FIRST, BEHAVIOR_ALL, BEHAVIOR_EACH]),
            ),
            probatio.Optional(CONF_FOR): cv.positive_time_period,
        },
    }
)


class NotTriggeredReasonReporter(Protocol):
    """Reports why an evaluated change did not fire an entity trigger."""

    def __call__(self, reason: str, /, **data: Any) -> None:
        """Report, with diagnostic data, why the change did not fire."""


def _report_not_triggered_noop(reason: str, /, **data: Any) -> None:
    """Swallow a not-triggered report; used when diagnostics are not wanted."""


class EntityTriggerBase(Trigger):
    """Trigger for entity state changes."""

    _domain_specs: Mapping[str, DomainSpec]
    # States filtered from the to_state pre-filter (and `_should_include`).
    _excluded_states: Final[frozenset[str]] = frozenset(
        {STATE_UNAVAILABLE, STATE_UNKNOWN}
    )
    # States filtered from the from_state pre-filter. Defaults to
    # `_excluded_states`. Subclasses can override to relax the origin
    # check.
    _excluded_from_states: ClassVar[frozenset[str]] = _excluded_states
    _schema: probatio.Schema = ENTITY_STATE_TRIGGER_SCHEMA_WITH_BEHAVIOR
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

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the state trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.target is not None
        self._options = config.options or {}
        self._duration: timedelta | None = self._options.get(CONF_FOR)
        self._target = config.target

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Filter entities matching any of the domain specs."""
        return filter_by_domain_specs(self._hass, self._domain_specs, entities)

    def _get_tracked_value(self, state: State) -> Any:
        """Get the tracked value from a state based on the DomainSpec."""
        domain_spec = self._domain_specs[state.domain]
        if domain_spec.value_source is None:
            return state.state
        return state.attributes.get(domain_spec.value_source)

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the transition should fire the trigger.

        Called only after `from_state.state` has been filtered against
        `_excluded_from_states` and `to_state.state` against
        `_excluded_states`, so subclasses don't need to repeat those
        checks. Default: any state change. Override to add semantics
        (specific from/to states, value changed across a threshold,
        etc.).
        """
        return from_state.state != to_state.state

    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check if the state is a target state for the trigger.

        Called only after `state.state` has been filtered against
        `_excluded_states`, so subclasses don't need to repeat that
        check. Default: any non-excluded state is a target. Override
        to restrict (specific to_states, value within a threshold,
        etc.).

        When the state cannot fire the trigger, subclasses may use
        `report_not_triggered` to record an interesting reason - e.g. a
        non-numeric value or an unsupported unit - in the automation trace.
        Callers that don't collect diagnostics (e.g. `count_matches`) pass
        `_report_not_triggered_noop`.
        """
        return True

    def _should_include(self, state: State) -> bool:
        """Check if an entity should participate in all/count checks.

        The default implementation excludes only entities whose state.state
        is in `_excluded_states` (unavailable / unknown). Subclasses can
        override to also exclude entities that lack the optional capability
        the trigger relies on (e.g. a missing volume_level attribute).
        """
        return state.state not in self._excluded_states

    def count_matches(
        self,
        entity_ids: Iterable[str],
        states: Mapping[str, State | None] | None = None,
    ) -> tuple[int, int]:
        """Return (matches, included) for the entity set.

        `matches` is the number of entities that pass `_should_include` AND
        `is_valid_state`. `included` is the number that pass
        `_should_include` (i.e. are visible to the all/count check at all).
        Callers can use the pair to distinguish vacuous truth
        (`included == 0`) from a genuine all-match
        (`matches == included > 0`).

        Entity states are read from `states` when provided, otherwise from
        the live state machine. Pass the targeted entity states received
        with a state change event to evaluate the event against the states
        as they were when the event fired.
        """
        matches = 0
        included = 0
        for entity_id in entity_ids:
            if states is not None:
                state = states[entity_id]
            else:
                state = self._hass.states.get(entity_id)
            if state is None or not self._should_include(state):
                continue
            included += 1
            if self.is_valid_state(state, _report_not_triggered_noop):
                matches += 1
        return matches, included

    @callback
    def _cancel_invalidated_timers(
        self,
        behavior: str,
        pending_timers: dict[str, CALLBACK_TYPE],
        target_state_change_data: TargetStateChangedData,
    ) -> None:
        """Cancel pending duration timers invalidated by a state change.

        Runs on every delivered state change, before the trigger's own
        validity checks: an event which cannot fire the trigger, e.g. an
        entity becoming unavailable, may still invalidate a pending timer.
        The targeted entity states have already been updated with this
        event, so the first/all check can simply recount.
        """
        event = target_state_change_data.state_change_event
        if behavior == BEHAVIOR_EACH:
            entity_id = event.data["entity_id"]
            if entity_id not in pending_timers:
                return
            to_state = event.data["new_state"]
            if (
                to_state is None
                or to_state.state in self._excluded_states
                or not self.is_valid_state(to_state, _report_not_triggered_noop)
            ):
                pending_timers.pop(entity_id)()
            return
        if behavior not in pending_timers:
            return
        if not self._combined_state_still_valid(
            behavior,
            target_state_change_data.targeted_entity_ids,
            target_state_change_data.targeted_entity_states,
        ):
            pending_timers.pop(behavior)()

    def _combined_state_still_valid(
        self,
        behavior: str,
        entity_ids: Iterable[str],
        states: Mapping[str, State | None],
    ) -> bool:
        """Check the combined first/all state for a pending duration timer."""
        matches, included = self.count_matches(entity_ids, states)
        if behavior == BEHAVIOR_FIRST:
            return matches >= 1
        # Require at least one included entity to avoid keeping the timer
        # alive when every targeted entity has been filtered out since it
        # started — a vacuous all-match (`included == 0`) would otherwise
        # let the action fire after `for:` even though no entity still
        # matches.
        return included > 0 and matches == included

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        behavior: str = self._options.get(ATTR_BEHAVIOR, BEHAVIOR_EACH)
        # Pending `for:` duration timers, keyed by entity_id for behavior
        # each and by the behavior for first/all.
        pending_timers: dict[str, CALLBACK_TYPE] = {}

        @callback
        def handle_entities_update(
            added: set[str],
            removed: set[str],
            entity_states: Mapping[str, State | None],
        ) -> None:
            """Re-validate pending duration timers on target changes.

            Timers of entities no longer targeted are cancelled, and the
            combined first/all condition is recounted over the updated
            target: e.g. a non-matching entity added to the target breaks a
            pending all-match.
            """
            for entity_id in removed:
                if (cancel := pending_timers.pop(entity_id, None)) is not None:
                    cancel()
            if behavior not in pending_timers:
                return
            if not self._combined_state_still_valid(
                behavior, entity_states.keys(), entity_states
            ):
                pending_timers.pop(behavior)()

        @callback
        def state_change_listener(
            target_state_change_data: TargetStateChangedData,
        ) -> None:
            """Listen for state changes and call action."""
            event = target_state_change_data.state_change_event
            entity_id = event.data["entity_id"]
            from_state = event.data["old_state"]
            to_state = event.data["new_state"]

            if pending_timers:
                self._cancel_invalidated_timers(
                    behavior, pending_timers, target_state_change_data
                )

            if not from_state or not to_state:
                return

            if to_state.state in self._excluded_states:
                return

            @callback
            def report_not_triggered(reason: str, /, **data: Any) -> None:
                """Report why this evaluated change did not fire the trigger."""
                if did_not_trigger is None:
                    return
                did_not_trigger(
                    NotTriggeredInfo(reason=reason, data=data), event.context
                )

            if not self.is_valid_state(to_state, report_not_triggered):
                return

            if (
                from_state.state in self._excluded_from_states
                or not self.is_valid_transition(from_state, to_state)
            ):
                return

            # Count against the targeted entity states as of this event, not
            # the live state machine: state change events are dispatched one
            # event loop iteration after the state machine is updated, so the
            # state machine may already contain later changes to other
            # targeted entities.
            if behavior == BEHAVIOR_ALL:
                matches, included = self.count_matches(
                    target_state_change_data.targeted_entity_ids,
                    target_state_change_data.targeted_entity_states,
                )
                if matches != included:
                    return
            elif behavior == BEHAVIOR_FIRST:
                # Note: It's enough to test for exactly 1 match here because if there
                # were previously 2 matches the transition would not be valid and we
                # would have returned already.
                matches, _ = self.count_matches(
                    target_state_change_data.targeted_entity_ids,
                    target_state_change_data.targeted_entity_states,
                )
                if matches != 1:
                    return

            @callback
            def call_action() -> None:
                """Call action with right context."""
                run_action(
                    {
                        ATTR_ENTITY_ID: entity_id,
                        "from_state": from_state,
                        "to_state": to_state,
                        "for": self._duration,
                    },
                    f"state of {entity_id}",
                    event.context,
                )

            if not self._duration:
                call_action()
                return

            subscription_key = entity_id if behavior == BEHAVIOR_EACH else behavior
            if (
                previous_timer := pending_timers.pop(subscription_key, None)
            ) is not None:
                previous_timer()

            @callback
            def fire_after_duration(_now: datetime) -> None:
                """Fire the action once the state has held for the duration."""
                del pending_timers[subscription_key]
                call_action()

            pending_timers[subscription_key] = async_call_later(
                self._hass, self._duration, fire_after_duration
            )

        unsub = await async_track_target_selector_state_change_event(
            self._hass,
            self._target,
            state_change_listener,
            self.entity_filter,
            handle_entities_update if self._duration else None,
            primary_entities_only=self._primary_entities_only,
        )

        @callback
        def async_remove() -> None:
            """Remove state listeners async."""
            unsub()
            for cancel_timer in pending_timers.values():
                cancel_timer()
            pending_timers.clear()

        return async_remove


class EntityTargetStateTriggerBase(EntityTriggerBase):
    """Trigger for entity state changes to a specific state.

    Uses _get_tracked_value to extract the value, so it works for both
    state-based and attribute-based triggers depending on the DomainSpec.
    """

    _to_states: set[str]

    @override
    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check the value changed and the origin was not already a target state."""
        from_value = self._get_tracked_value(from_state)
        return (
            from_value != self._get_tracked_value(to_state)
            and from_value not in self._to_states
        )

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check if the new state matches the expected state."""
        return self._get_tracked_value(state) in self._to_states


class EntityTransitionTriggerBase(EntityTriggerBase):
    """Trigger for entity state changes between specific states."""

    _from_states: set[str | bool]
    _to_states: set[str | bool]

    @override
    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state matches the expected ones."""
        from_value = self._get_tracked_value(from_state)
        return (
            from_value != self._get_tracked_value(to_state)
            and from_value in self._from_states
        )

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check if the new state matches the expected states."""
        return self._get_tracked_value(state) in self._to_states


class EntityOriginStateTriggerBase(EntityTriggerBase):
    """Trigger for entity state changes from a specific state."""

    _from_state: str

    @override
    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if origin state matches expected and that the state changed."""
        return bool(
            self._get_tracked_value(from_state) == self._from_state
            and self._get_tracked_value(to_state) != self._from_state
        )

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check that the new state is different from the origin state."""
        return bool(self._get_tracked_value(state) != self._from_state)


class StatelessEntityTriggerBase(EntityTriggerBase):
    """Trigger for entities that don't carry meaningful state.

    Used for stateless entities (buttons, scenes, doorbells, events)
    whose `state.state` is just a timestamp of the last activation.
    `STATE_UNKNOWN` is a legitimate prior state — the first activation
    after startup must still fire the trigger.
    """

    _schema: probatio.Schema = ENTITY_STATE_TRIGGER_SCHEMA
    _excluded_from_states: ClassVar[frozenset[str]] = frozenset({STATE_UNAVAILABLE})


NUMERICAL_ATTRIBUTE_CHANGED_TRIGGER_SCHEMA = ENTITY_STATE_TRIGGER_SCHEMA.extend(
    {
        probatio.Required(CONF_OPTIONS, default={}): probatio.All(
            {
                probatio.Required("threshold"): NumericThresholdSelector(
                    NumericThresholdSelectorConfig(mode=NumericThresholdMode.CHANGED)
                )
            },
        )
    }
)


class EntityNumericalStateTriggerBase(EntityTriggerBase):
    """Base class for numerical state and state attribute triggers."""

    _valid_unit: str | UndefinedType | None = UNDEFINED
    _threshold_type: NumericThresholdType

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the state trigger."""
        super().__init__(hass, config)
        threshold_options: dict[str, Any] = self._options["threshold"]
        self.threshold = ThresholdConfig.from_config(threshold_options.get("value"))
        self.lower_threshold = ThresholdConfig.from_config(
            threshold_options.get("value_min")
        )
        self.upper_threshold = ThresholdConfig.from_config(
            threshold_options.get("value_max")
        )
        self._threshold_type = threshold_options["type"]

    def _is_valid_unit(self, unit: str | None) -> bool:
        """Check if the given unit is valid for this trigger."""
        if isinstance(self._valid_unit, UndefinedType):
            return True
        return unit == self._valid_unit

    def _get_threshold_value(
        self,
        threshold: ThresholdConfig | None,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> float | None:
        """Get threshold value from float or entity state."""
        if threshold is None:
            return None
        if threshold.numerical:
            return threshold.number

        if not (state := self._hass.states.get(threshold.entity)):  # type: ignore[arg-type]
            # Entity not found
            report_not_triggered(
                "threshold_entity_not_found",
                entity_id=threshold.entity,
            )
            return None
        unit = state.attributes.get(EntityStateAttribute.UNIT_OF_MEASUREMENT)
        if not self._is_valid_unit(unit):
            # Entity unit does not match the expected unit
            report_not_triggered(
                "threshold_unit_not_supported",
                entity_id=threshold.entity,
                unit=unit,
            )
            return None
        try:
            return float(state.state)
        except TypeError, ValueError:
            # Entity state is not a valid number
            report_not_triggered(
                "threshold_value_not_numeric",
                entity_id=threshold.entity,
                value=state.state,
            )
            return None

    @override
    def _get_tracked_value(self, state: State) -> float | None:
        """Get the tracked numerical value from a state."""
        domain_spec = self._domain_specs[state.domain]
        raw_value: Any
        if domain_spec.value_source is None:
            if not self._is_valid_unit(
                state.attributes.get(EntityStateAttribute.UNIT_OF_MEASUREMENT)
            ):
                return None
            raw_value = state.state
        else:
            raw_value = state.attributes.get(domain_spec.value_source)

        try:
            return float(raw_value)
        except TypeError, ValueError:
            # Entity state is not a valid number
            return None

    def _report_tracked_value_problem(
        self, state: State, report_not_triggered: NotTriggeredReasonReporter
    ) -> None:
        """Report why `_get_tracked_value` rejected this state.

        Called only when the tracked value is invalid. It mirrors the failure
        modes of `_get_tracked_value` - which integrations override, so the
        reason is derived here rather than reported inline: a state-sourced
        value with an unsupported unit, otherwise a value that is not a number.
        """
        domain_spec = self._domain_specs[state.domain]
        raw_value: Any
        if domain_spec.value_source is None:
            unit = state.attributes.get(EntityStateAttribute.UNIT_OF_MEASUREMENT)
            if not self._is_valid_unit(unit):
                report_not_triggered(
                    "entity_unit_not_supported",
                    entity_id=state.entity_id,
                    unit=unit,
                )
                return
            raw_value = state.state
        else:
            raw_value = state.attributes.get(domain_spec.value_source)
        report_not_triggered(
            "entity_value_not_numeric",
            entity_id=state.entity_id,
            value=raw_value,
        )

    @override
    def is_valid_state(
        self,
        state: State,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> bool:
        """Check if the new state or state attribute matches the expected one."""
        # Handle missing or None value case first to avoid expensive exceptions
        if (current_value := self._get_tracked_value(state)) is None:
            self._report_tracked_value_problem(state, report_not_triggered)
            return False

        if self._threshold_type == NumericThresholdType.ANY:
            # If the threshold type is "any" we always trigger on valid state
            # changes
            return True

        if self._threshold_type == NumericThresholdType.ABOVE:
            if (
                limit := self._get_threshold_value(self.threshold, report_not_triggered)
            ) is None:
                # Entity not found or invalid number, don't trigger
                return False
            return current_value > limit
        if self._threshold_type == NumericThresholdType.BELOW:
            if (
                limit := self._get_threshold_value(self.threshold, report_not_triggered)
            ) is None:
                # Entity not found or invalid number, don't trigger
                return False
            return current_value < limit

        # Mode is BETWEEN or OUTSIDE. Evaluate the lower limit first so at most
        # one not-triggered reason is reported per change.
        lower_limit = self._get_threshold_value(
            self.lower_threshold, report_not_triggered
        )
        if lower_limit is None:
            # Entity not found or invalid number, don't trigger
            return False
        upper_limit = self._get_threshold_value(
            self.upper_threshold, report_not_triggered
        )
        if upper_limit is None:
            # Entity not found or invalid number, don't trigger
            return False
        between = lower_limit <= current_value <= upper_limit
        if self._threshold_type == NumericThresholdType.BETWEEN:
            return between
        return not between


class EntityNumericalStateTriggerWithUnitBase(EntityNumericalStateTriggerBase):
    """Base class for numerical state and state attribute triggers."""

    _base_unit: str | None  # Base unit for the tracked value
    _unit_converter: type[BaseUnitConverter]

    def _get_entity_unit(self, state: State) -> str | None:
        """Get the unit of an entity from its state."""
        return state.attributes.get(EntityStateAttribute.UNIT_OF_MEASUREMENT)

    @override
    def _report_tracked_value_problem(
        self, state: State, report_not_triggered: NotTriggeredReasonReporter
    ) -> None:
        """Report why `_get_tracked_value` rejected this state.

        Mirrors the with-unit failure modes: a value that is not a number,
        otherwise a unit that cannot be converted to the base unit.
        """
        domain_spec = self._domain_specs[state.domain]
        raw_value: Any
        if domain_spec.value_source is None:
            raw_value = state.state
        else:
            raw_value = state.attributes.get(domain_spec.value_source)
        try:
            float(raw_value)
        except TypeError, ValueError:
            report_not_triggered(
                "entity_value_not_numeric",
                entity_id=state.entity_id,
                value=raw_value,
            )
            return
        report_not_triggered(
            "entity_unit_not_supported",
            entity_id=state.entity_id,
            unit=self._get_entity_unit(state),
        )

    @override
    def _get_threshold_value(
        self,
        threshold: ThresholdConfig | None,
        report_not_triggered: NotTriggeredReasonReporter,
    ) -> float | None:
        """Get threshold value from float or entity state."""
        if threshold is None:
            return None
        if threshold.numerical:
            return self._unit_converter.convert(
                threshold.number,  # type: ignore[arg-type]
                threshold.unit,  # type: ignore[arg-type]
                self._base_unit,
            )

        if not (state := self._hass.states.get(threshold.entity)):  # type: ignore[arg-type]
            # Entity not found
            report_not_triggered(
                "threshold_entity_not_found",
                entity_id=threshold.entity,
            )
            return None
        try:
            value = float(state.state)
        except TypeError, ValueError:
            # Entity state is not a valid number
            report_not_triggered(
                "threshold_value_not_numeric",
                entity_id=threshold.entity,
                value=state.state,
            )
            return None

        unit = state.attributes.get(EntityStateAttribute.UNIT_OF_MEASUREMENT)
        try:
            return self._unit_converter.convert(value, unit, self._base_unit)
        except HomeAssistantError:
            # Unit conversion failed (i.e. incompatible units), treat as invalid number
            report_not_triggered(
                "threshold_unit_not_supported",
                entity_id=threshold.entity,
                unit=unit,
            )
            return None

    @override
    def _get_tracked_value(self, state: State) -> float | None:
        """Get the tracked numerical value from a state."""
        domain_spec = self._domain_specs[state.domain]
        raw_value: Any
        if domain_spec.value_source is None:
            raw_value = state.state
        else:
            raw_value = state.attributes.get(domain_spec.value_source)

        try:
            value = float(raw_value)
        except TypeError, ValueError:
            # Entity state is not a valid number
            return None

        try:
            return self._unit_converter.convert(
                value, self._get_entity_unit(state), self._base_unit
            )
        except HomeAssistantError:
            # Unit conversion failed (i.e. incompatible units), treat as invalid number
            return None


class EntityNumericalStateChangedTriggerBase(EntityNumericalStateTriggerBase):
    """Trigger for numerical state and state attribute changes."""

    _schema = NUMERICAL_ATTRIBUTE_CHANGED_TRIGGER_SCHEMA

    @override
    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the tracked numeric value has changed."""
        return self._get_tracked_value(from_state) != self._get_tracked_value(to_state)


def make_numerical_state_changed_with_unit_schema(
    unit_converter: type[BaseUnitConverter],
) -> probatio.Schema:
    """Factory for numerical state trigger schema with unit option."""
    return ENTITY_STATE_TRIGGER_SCHEMA.extend(
        {
            probatio.Required(CONF_OPTIONS, default={}): probatio.All(
                {
                    probatio.Required("threshold"): NumericThresholdSelector(
                        NumericThresholdSelectorConfig(
                            mode=NumericThresholdMode.CHANGED,
                            unit_of_measurement=list(unit_converter.VALID_UNITS),
                        )
                    )
                },
            )
        }
    )


class EntityNumericalStateChangedTriggerWithUnitBase(
    EntityNumericalStateChangedTriggerBase,
    EntityNumericalStateTriggerWithUnitBase,
):
    """Trigger for numerical state and state attribute changes."""

    @override
    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Create a schema."""
        super().__init_subclass__(**kwargs)
        cls._schema = make_numerical_state_changed_with_unit_schema(cls._unit_converter)


NUMERICAL_ATTRIBUTE_CROSSED_THRESHOLD_SCHEMA = (
    ENTITY_STATE_TRIGGER_SCHEMA_WITH_BEHAVIOR.extend(
        {
            probatio.Required(CONF_OPTIONS): {
                probatio.Required("threshold"): NumericThresholdSelector(
                    NumericThresholdSelectorConfig(mode=NumericThresholdMode.CROSSED)
                ),
            },
        }
    )
)


class EntityNumericalStateCrossedThresholdTriggerBase(EntityNumericalStateTriggerBase):
    """Trigger for numerical state and state attribute changes.

    This trigger only fires when the observed attribute
    changes from not within to within the defined threshold.
    """

    _schema = NUMERICAL_ATTRIBUTE_CROSSED_THRESHOLD_SCHEMA

    @override
    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check that the tracked value crossed into the threshold range."""
        return not self.is_valid_state(from_state, _report_not_triggered_noop)


def _make_numerical_state_crossed_threshold_with_unit_schema(
    unit_converter: type[BaseUnitConverter],
) -> probatio.Schema:
    """Trigger for numerical state and state attribute changes.

    This trigger only fires when the observed attribute
    changes from not within to within the defined threshold.
    """
    return ENTITY_STATE_TRIGGER_SCHEMA_WITH_BEHAVIOR.extend(
        {
            probatio.Required(CONF_OPTIONS, default={}): {
                probatio.Required("threshold"): NumericThresholdSelector(
                    NumericThresholdSelectorConfig(
                        mode=NumericThresholdMode.CROSSED,
                        unit_of_measurement=list(unit_converter.VALID_UNITS),
                    )
                ),
            },
        }
    )


class EntityNumericalStateCrossedThresholdTriggerWithUnitBase(
    EntityNumericalStateCrossedThresholdTriggerBase,
    EntityNumericalStateTriggerWithUnitBase,
):
    """Trigger for numerical state and state attribute changes."""

    @override
    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Create a schema."""
        super().__init_subclass__(**kwargs)
        cls._schema = _make_numerical_state_crossed_threshold_with_unit_schema(
            cls._unit_converter
        )


def _normalize_domain_specs(
    domain_specs: Mapping[str, DomainSpec] | str,
) -> Mapping[str, DomainSpec]:
    """Normalize domain_specs argument to a Mapping."""
    if isinstance(domain_specs, str):
        return {domain_specs: DomainSpec()}
    return domain_specs


def make_entity_target_state_trigger(
    domain_specs: Mapping[str, DomainSpec] | str,
    to_states: str | set[str],
    *,
    primary_entities_only: bool = True,
) -> type[EntityTargetStateTriggerBase]:
    """Create a trigger for entity state changes to specific state(s).

    domain_specs can be a string (domain name) for simple state-based triggers,
    or a Mapping[str, DomainSpec] for attribute-based or multi-domain triggers.
    """
    specs = _normalize_domain_specs(domain_specs)

    if isinstance(to_states, str):
        to_states_set = {to_states}
    else:
        to_states_set = to_states

    class CustomTrigger(EntityTargetStateTriggerBase):
        """Trigger for entity state changes."""

        _domain_specs = specs
        _to_states = to_states_set
        _primary_entities_only = primary_entities_only

    return CustomTrigger


def make_entity_transition_trigger(
    domain_specs: Mapping[str, DomainSpec] | str,
    *,
    from_states: set[str | bool],
    to_states: set[str | bool],
) -> type[EntityTransitionTriggerBase]:
    """Create a trigger for entity state changes between specific states.

    domain_specs can be a string (domain name) for simple state-based triggers,
    or a Mapping[str, DomainSpec] for attribute-based or multi-domain triggers.
    """
    specs = _normalize_domain_specs(domain_specs)

    class CustomTrigger(EntityTransitionTriggerBase):
        """Trigger for conditional entity state changes."""

        _domain_specs = specs
        _from_states = from_states
        _to_states = to_states

    return CustomTrigger


def make_entity_origin_state_trigger(
    domain_specs: Mapping[str, DomainSpec] | str,
    *,
    from_state: str,
) -> type[EntityOriginStateTriggerBase]:
    """Create a trigger for entity state changes from a specific state.

    domain_specs can be a string (domain name) for simple state-based triggers,
    or a Mapping[str, DomainSpec] for attribute-based or multi-domain triggers.
    """
    specs = _normalize_domain_specs(domain_specs)

    class CustomTrigger(EntityOriginStateTriggerBase):
        """Trigger for entity "from state" changes."""

        _domain_specs = specs
        _from_state = from_state

    return CustomTrigger


def make_entity_numerical_state_changed_trigger(
    domain_specs: Mapping[str, DomainSpec],
    valid_unit: str | UndefinedType | None = UNDEFINED,
    *,
    primary_entities_only: bool = True,
) -> type[EntityNumericalStateChangedTriggerBase]:
    """Create a trigger for numerical state value change."""

    class CustomTrigger(EntityNumericalStateChangedTriggerBase):
        """Trigger for numerical state value changes."""

        _domain_specs = domain_specs
        _valid_unit = valid_unit
        _primary_entities_only = primary_entities_only

    return CustomTrigger


def make_entity_numerical_state_crossed_threshold_trigger(
    domain_specs: Mapping[str, DomainSpec],
    valid_unit: str | UndefinedType | None = UNDEFINED,
    *,
    primary_entities_only: bool = True,
) -> type[EntityNumericalStateCrossedThresholdTriggerBase]:
    """Create a trigger for numerical state value crossing a threshold."""

    class CustomTrigger(EntityNumericalStateCrossedThresholdTriggerBase):
        """Trigger for numerical state value crossing a threshold."""

        _domain_specs = domain_specs
        _valid_unit = valid_unit
        _primary_entities_only = primary_entities_only

    return CustomTrigger


def make_entity_numerical_state_changed_with_unit_trigger(
    domain_specs: Mapping[str, DomainSpec],
    base_unit: str,
    unit_converter: type[BaseUnitConverter],
) -> type[EntityNumericalStateChangedTriggerWithUnitBase]:
    """Create a trigger for numerical state value change."""

    class CustomTrigger(EntityNumericalStateChangedTriggerWithUnitBase):
        """Trigger for numerical state value changes."""

        _domain_specs = domain_specs
        _base_unit = base_unit
        _unit_converter = unit_converter

    return CustomTrigger


def make_entity_numerical_state_crossed_threshold_with_unit_trigger(
    domain_specs: Mapping[str, DomainSpec],
    base_unit: str,
    unit_converter: type[BaseUnitConverter],
) -> type[EntityNumericalStateCrossedThresholdTriggerWithUnitBase]:
    """Create a trigger for numerical state value crossing a threshold."""

    class CustomTrigger(EntityNumericalStateCrossedThresholdTriggerWithUnitBase):
        """Trigger for numerical state value crossing a threshold."""

        _domain_specs = domain_specs
        _base_unit = base_unit
        _unit_converter = unit_converter

    return CustomTrigger
