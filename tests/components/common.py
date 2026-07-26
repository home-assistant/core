"""Shared test helpers for components."""

from collections.abc import Iterable
import copy
from enum import StrEnum
import itertools
import logging
from pathlib import Path
from typing import Any, TypedDict

import pytest
import voluptuous as vol

from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_CONDITION,
    CONF_ENTITY_ID,
    CONF_OPTIONS,
    CONF_PLATFORM,
    CONF_TARGET,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)
from homeassistant.helpers.condition import (
    ConditionCheckerTypeOptional,
    async_from_config as async_condition_from_config,
    async_validate_condition_config,
)
from homeassistant.helpers.trigger import (
    async_initialize_triggers,
    async_validate_trigger_config,
)
from homeassistant.helpers.typing import UNDEFINED, TemplateVarsType, UndefinedType
from homeassistant.util.yaml import load_yaml_dict

from tests.common import MockConfigEntry, mock_device_registry


async def target_entities(
    hass: HomeAssistant,
    domain: str,
    *,
    domain_excluded: str | None = None,
    entity_category: EntityCategory | None = None,
) -> dict[str, list[str]]:
    """Create multiple entities associated with different targets.

    If `domain_excluded` is provided, entities in excluded_entities will have this
    domain, otherwise they will have the same domain as included_entities.

    If `entity_category` is provided, all created registry entities (i.e. the
    area-, device-, and label-associated entities) are created with that
    entity category. Standalone entities are referenced directly by entity_id
    and are unaffected.

    Returns a dict with the following keys:
    - included_entities: List of entity_ids meant to be targeted.
    - excluded_entities: List of entity_ids not meant to be targeted.
    """
    domain_excluded = domain_excluded or domain

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    floor_reg = fr.async_get(hass)
    floor = floor_reg.async_get_floor_by_name("Test Floor") or floor_reg.async_create(
        "Test Floor"
    )

    area_reg = ar.async_get(hass)
    area = area_reg.async_get_area_by_name("Test Area") or area_reg.async_create(
        "Test Area", floor_id=floor.floor_id
    )

    label_reg = lr.async_get(hass)
    label = label_reg.async_get_label_by_name("Test Label") or label_reg.async_create(
        "Test Label"
    )

    device = dr.DeviceEntry(
        config_entry_id=config_entry.entry_id,
        id="test_device",
        area_id=area.id,
        labels={label.label_id},
    )
    mock_device_registry(hass, {device.id: device})

    entity_reg = er.async_get(hass)
    # Entities associated with area
    entity_area = entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_area",
        suggested_object_id=f"area_{domain}",
        entity_category=entity_category,
    )
    entity_reg.async_update_entity(entity_area.entity_id, area_id=area.id)
    entity_area_excluded = entity_reg.async_get_or_create(
        domain=domain_excluded,
        platform="test",
        unique_id=f"{domain_excluded}_area_excluded",
        suggested_object_id=f"area_{domain_excluded}_excluded",
        entity_category=entity_category,
    )
    entity_reg.async_update_entity(entity_area_excluded.entity_id, area_id=area.id)

    # Entities associated with device
    entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_device",
        suggested_object_id=f"device_{domain}",
        device_id=device.id,
        entity_category=entity_category,
    )
    entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_device2",
        suggested_object_id=f"device2_{domain}",
        device_id=device.id,
        entity_category=entity_category,
    )
    entity_reg.async_get_or_create(
        domain=domain_excluded,
        platform="test",
        unique_id=f"{domain_excluded}_device_excluded",
        suggested_object_id=f"device_{domain_excluded}_excluded",
        device_id=device.id,
        entity_category=entity_category,
    )

    # Entities associated with label
    entity_label = entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_label",
        suggested_object_id=f"label_{domain}",
        entity_category=entity_category,
    )
    entity_reg.async_update_entity(entity_label.entity_id, labels={label.label_id})
    entity_label_excluded = entity_reg.async_get_or_create(
        domain=domain_excluded,
        platform="test",
        unique_id=f"{domain_excluded}_label_excluded",
        suggested_object_id=f"label_{domain_excluded}_excluded",
        entity_category=entity_category,
    )
    entity_reg.async_update_entity(
        entity_label_excluded.entity_id, labels={label.label_id}
    )

    # Return all available entities
    return {
        "included_entities": [
            f"{domain}.standalone_{domain}",
            f"{domain}.standalone2_{domain}",
            f"{domain}.label_{domain}",
            f"{domain}.area_{domain}",
            f"{domain}.device_{domain}",
            f"{domain}.device2_{domain}",
        ],
        "excluded_entities": [
            f"{domain_excluded}.standalone_{domain_excluded}_excluded",
            f"{domain_excluded}.label_{domain_excluded}_excluded",
            f"{domain_excluded}.area_{domain_excluded}_excluded",
            f"{domain_excluded}.device_{domain_excluded}_excluded",
        ],
    }


def parametrize_target_entities(domain: str) -> list[tuple[dict, str, int]]:
    """Parametrize target entities for different target types.

    Meant to be used with target_entities.
    """
    return [
        (
            {
                CONF_ENTITY_ID: [
                    f"{domain}.standalone_{domain}",
                    f"{domain}.standalone2_{domain}",
                ]
            },
            f"{domain}.standalone_{domain}",
            2,
        ),
        ({ATTR_LABEL_ID: "test_label"}, f"{domain}.label_{domain}", 3),
        ({ATTR_AREA_ID: "test_area"}, f"{domain}.area_{domain}", 3),
        ({ATTR_FLOOR_ID: "test_floor"}, f"{domain}.area_{domain}", 3),
        ({ATTR_LABEL_ID: "test_label"}, f"{domain}.device_{domain}", 3),
        ({ATTR_AREA_ID: "test_area"}, f"{domain}.device_{domain}", 3),
        ({ATTR_FLOOR_ID: "test_floor"}, f"{domain}.device_{domain}", 3),
        ({ATTR_DEVICE_ID: "test_device"}, f"{domain}.device_{domain}", 2),
    ]


class StateDescription(TypedDict):
    """Test state with attributes."""

    state: str | None
    attributes: dict


class BasicTriggerStateDescription(TypedDict):
    """Test state and expected service call count for targeted entities only."""

    included_state: StateDescription  # State for entities meant to be targeted
    count: int  # Expected service call count


class TriggerStateDescription(BasicTriggerStateDescription):
    """Test state and expected service call count.

    Covers both included and excluded entities.
    """

    excluded_state: StateDescription  # State for entities not meant to be targeted
    # State for the *other* targeted entities (the ones not under direct test).
    # Usually equal to `included_state`; differs when the test exercises a
    # scenario where targeted-but-not-under-test entities sit in a state that
    # the trigger's `_should_include` method filters out of the all/count
    # checks.
    others_state: StateDescription


class ConditionStateDescription(TypedDict):
    """Test state and expected condition evaluation."""

    included_state: StateDescription  # State for entities meant to be targeted
    excluded_state: StateDescription  # State for entities not meant to be targeted

    condition_true: bool  # If the condition is expected to evaluate to true
    # If the condition is expected to evaluate to true
    # for the first targeted entity
    condition_true_first_entity: bool


def _parametrize_condition_states(
    *,
    condition: str,
    condition_options: dict[str, Any] | None = None,
    target_states: list[str | None | tuple[str | None, dict]],
    other_states: list[str | None | tuple[str | None, dict]],
    extra_excluded_states: list[str | None | tuple[str | None, dict]] | None = None,
    required_filter_attributes: dict | None,
    condition_true_if_invalid: bool,
    excluded_entities_from_other_domain: bool,
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize states and expected condition evaluations.

    The target_states and other_states iterables are either iterables of
    states or iterables of (state, attributes) tuples.

    Returns a list of tuples with (condition, condition options, list of states),
    where states is a list of ConditionStateDescription dicts.
    """

    required_filter_attributes = required_filter_attributes or {}
    condition_options = condition_options or {}
    extra_excluded_states = extra_excluded_states or []
    add_excluded_state = excluded_entities_from_other_domain or bool(
        required_filter_attributes
    )

    def state_with_attributes(
        state: str | None | tuple[str | None, dict],
        condition_true: bool,
        condition_true_first_entity: bool,
    ) -> ConditionStateDescription:
        """Return ConditionStateDescription dict."""
        if isinstance(state, str) or state is None:
            return {
                "included_state": {
                    "state": state,
                    "attributes": required_filter_attributes,
                },
                "excluded_state": {
                    "state": state if add_excluded_state else None,
                    "attributes": {},
                },
                "condition_true": condition_true,
                "condition_true_first_entity": condition_true_first_entity,
            }
        return {
            "included_state": {
                "state": state[0],
                "attributes": state[1] | required_filter_attributes,
            },
            "excluded_state": {
                "state": state[0] if add_excluded_state else None,
                "attributes": state[1] if add_excluded_state else {},
            },
            "condition_true": condition_true,
            "condition_true_first_entity": condition_true_first_entity,
        }

    return [
        (
            condition,
            condition_options,
            list(
                itertools.chain(
                    (state_with_attributes(None, condition_true_if_invalid, True),),
                    (
                        state_with_attributes(
                            STATE_UNAVAILABLE, condition_true_if_invalid, True
                        ),
                    ),
                    (
                        state_with_attributes(
                            STATE_UNKNOWN, condition_true_if_invalid, True
                        ),
                    ),
                    # `extra_excluded_states` are filtered by the condition's
                    # `_should_include` override exactly like
                    # missing/unavailable/unknown, so they share the
                    # `condition_true_if_invalid` expectation: vacuous True
                    # under behavior=all (every entity filtered → all-check
                    # vacuous), vacuous False under behavior=any.
                    (
                        state_with_attributes(
                            extra_excluded_state, condition_true_if_invalid, True
                        )
                        for extra_excluded_state in extra_excluded_states
                    ),
                    (
                        state_with_attributes(other_state, False, False)
                        for other_state in other_states
                    ),
                ),
            ),
        ),
        # Test each target state individually to isolate condition_true expectations
        *(
            (
                condition,
                condition_options,
                [
                    state_with_attributes(other_states[0], False, False),
                    state_with_attributes(target_state, True, False),
                ],
            )
            for target_state in target_states
        ),
    ]


def parametrize_condition_states_any(
    *,
    condition: str,
    condition_options: dict[str, Any] | None = None,
    target_states: list[str | None | tuple[str | None, dict]],
    other_states: list[str | None | tuple[str | None, dict]],
    extra_excluded_states: list[str | None | tuple[str | None, dict]] | None = None,
    required_filter_attributes: dict | None = None,
    excluded_entities_from_other_domain: bool = False,
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize states and expected evaluations for a condition under behavior=any.

    Returns a list of `(condition, condition_options, states)` tuples, where
    `states` is a list of ConditionStateDescription dicts. Each dict carries
    the state to apply to the entity under test, the state to apply to
    entities outside the target, the expected condition evaluation after the
    entity under test alone has been set, and the expected evaluation after
    every other targeted entity has been set to the same state.

    Args:
        condition: Condition key, e.g. `"climate.is_target_humidity"`.
        condition_options: Options dict passed to the condition (typically
            includes the `threshold` block); merged into each generated tuple.
        target_states: States the condition is expected to evaluate True
            for. Entries are either bare state values or `(state, attributes)`
            tuples.
        other_states: States the condition is expected to evaluate False for.
            Same accepted shapes as `target_states`. With behavior=any, an
            entity in such a state does not satisfy the condition.
        extra_excluded_states: *Additional* states (on top of the always-
            excluded missing/unavailable/unknown states) that the
            condition's `_should_include` override is expected to filter out.
            Under behavior=any, every targeted entity sitting in a filtered
            state yields `any([]) → False`, so these share the built-in
            invalid states' expectation. Set this for conditions whose
            `_should_include` skips entities lacking the tracked attribute.
        required_filter_attributes: Attributes that must be present on the
            entity for the condition's domain filter to accept it. The
            helper merges these into every generated state so the entity
            satisfies the filter; entities outside the target receive the
            same state value but *without* these attributes.
        excluded_entities_from_other_domain: When True, the helper assumes
            entities outside the target sit in another domain entirely;
            their state value is preserved (rather than being replaced with
            None) so the test verifies the condition ignores them by domain.
    """

    return _parametrize_condition_states(
        condition=condition,
        condition_options=condition_options,
        target_states=target_states,
        other_states=other_states,
        extra_excluded_states=extra_excluded_states,
        required_filter_attributes=required_filter_attributes,
        condition_true_if_invalid=False,
        excluded_entities_from_other_domain=excluded_entities_from_other_domain,
    )


def parametrize_condition_states_all(
    *,
    condition: str,
    condition_options: dict[str, Any] | None = None,
    target_states: list[str | None | tuple[str | None, dict]],
    other_states: list[str | None | tuple[str | None, dict]],
    extra_excluded_states: list[str | None | tuple[str | None, dict]] | None = None,
    required_filter_attributes: dict | None = None,
    excluded_entities_from_other_domain: bool = False,
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize states and expected evaluations for a condition under behavior=all.

    Returns a list of `(condition, condition_options, states)` tuples, where
    `states` is a list of ConditionStateDescription dicts. Each dict carries
    the state to apply to the entity under test, the state to apply to
    entities outside the target, the expected condition evaluation after the
    entity under test alone has been set, and the expected evaluation after
    every other targeted entity has been set to the same state.

    Args:
        condition: Condition key, e.g. `"climate.is_target_humidity"`.
        condition_options: Options dict passed to the condition (typically
            includes the `threshold` block); merged into each generated tuple.
        target_states: States the condition is expected to evaluate True for
            (i.e. entities in any such state contribute a "match" to the
            all-check). Entries are either bare state values or
            `(state, attributes)` tuples.
        other_states: States the condition is expected to evaluate False
            for. Same accepted shapes as `target_states`. Under behavior=all,
            an entity in such a state blocks the all-check (counts toward
            the check but is not a match).
        extra_excluded_states: *Additional* states (on top of the always-
            excluded/filtered-out missing/unavailable/unknown states) that
            the condition's `_should_include` override is expected to filter
            out. Under behavior=all, every targeted entity sitting in a
            filtered state yields `all([]) → True` (vacuous), so these share
            the built-in invalid states' expectation. Set this for
            conditions whose `_should_include` skips entities lacking the
            tracked attribute.
        required_filter_attributes: Attributes that must be present on the
            entity for the condition's domain filter to accept it. The
            helper merges these into every generated state so the entity
            satisfies the filter; entities outside the target receive the
            same state value but *without* these attributes.
        excluded_entities_from_other_domain: When True, the helper assumes
            entities outside the target sit in another domain entirely;
            their state value is preserved (rather than being replaced with
            None) so the test verifies the condition ignores them by domain.
    """

    return _parametrize_condition_states(
        condition=condition,
        condition_options=condition_options,
        target_states=target_states,
        other_states=other_states,
        extra_excluded_states=extra_excluded_states,
        required_filter_attributes=required_filter_attributes,
        condition_true_if_invalid=True,
        excluded_entities_from_other_domain=excluded_entities_from_other_domain,
    )


def parametrize_trigger_states(
    *,
    trigger: str,
    trigger_options: dict[str, Any] | None = None,
    target_states: list[str | None | tuple[str | None, dict]],
    other_states: list[str | None | tuple[str | None, dict]],
    extra_excluded_states: list[str | None | tuple[str | None, dict]] | None = None,
    extra_invalid_states: list[str | None | tuple[str | None, dict]] | None = None,
    required_filter_attributes: dict | None = None,
    trigger_from_none: bool = True,
    retrigger_on_target_state: bool = False,
) -> list[tuple[str, dict[str, Any], list[TriggerStateDescription]]]:
    """Parametrize sequences of states and expected service call counts.

    Returns a list of `(trigger, trigger_options, states)` tuples, where
    `states` is a list of TriggerStateDescription dicts describing the state
    sequence to drive the trigger through.

    The target_states, other_states, excluded_states, and extra_invalid_states
    iterables are either iterables of states or iterables of (state, attributes)
    tuples.

    `target_states` are states that should fire the trigger.

    `other_states` are states that should NOT fire the trigger and that DO
    count toward the all/count check (i.e. an entity in such a state blocks
    behavior=last).

    `extra_excluded_states` are *additional* states (on top of the always-
    included missing/unavailable/unknown that the base `_should_include`
    filters out) that the trigger's `_should_include` override is expected
    to filter out of the all/count check. The helper iterates over the full
    filtered set (`[None, STATE_UNAVAILABLE, STATE_UNKNOWN,
    *extra_excluded_states]`) and generates an additional pattern that sets
    the *other* targeted entities into each filtered state while the entity
    under test transitions to a target state — the trigger should fire even
    though the other entities never matched, because they are invisible to
    the all/count check.

    `extra_invalid_states` are *additional* states (on top of the always-
    included STATE_UNAVAILABLE and STATE_UNKNOWN) that should be treated as
    invalid by the trigger (i.e. `is_valid_transition` rejects transitions
    out of them). They drive the "transition from other state to invalid"
    and "initial state invalid" patterns alongside the built-in
    unavailable/unknown states.

    Set `trigger_from_none` to False if the trigger is not expected to fire
    when the initial state is None, this is relevant for triggers that limit
    entities to a certain device class because the device class can't be
    determined when the state is None.

    Set `retrigger_on_target_state` to True if the trigger is expected to fire
    when the state changes to another target state.
    """

    invalid_states = [
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
        *(extra_invalid_states or []),
    ]
    extra_excluded_states = list(extra_excluded_states or [])
    # The excluded_states pattern iterates over every state the base
    # _should_include impl filters out (a missing state object, unavailable,
    # unknown), plus any caller-supplied additions filtered by a
    # `_should_include` override.
    excluded_states = [
        None,
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
        *extra_excluded_states,
    ]
    required_filter_attributes = required_filter_attributes or {}
    trigger_options = trigger_options or {}

    def _included_state_desc(
        state: str | None | tuple[str | None, dict],
    ) -> StateDescription:
        """Build a state for entities meant to match the trigger's target.

        The required_filter_attributes are merged in so the state passes the
        trigger's filter.
        """
        if isinstance(state, str) or state is None:
            return {"state": state, "attributes": required_filter_attributes}
        return {
            "state": state[0],
            "attributes": state[1] | required_filter_attributes,
        }

    def _excluded_state_desc(
        state: str | None | tuple[str | None, dict],
    ) -> StateDescription:
        """Build a state for entities outside the trigger's target.

        The required_filter_attributes are intentionally NOT merged in so the
        state fails the trigger's filter. When the trigger has no filter, the
        excluded entity is fully irrelevant: its state value is set to None.
        """
        if isinstance(state, str) or state is None:
            return {
                "state": state if required_filter_attributes else None,
                "attributes": {},
            }
        return {
            "state": state[0] if required_filter_attributes else None,
            "attributes": state[1],
        }

    def state_with_attributes(
        state: str | None | tuple[str | None, dict],
        count: int,
        *,
        others_state: str | None | tuple[str | None, dict] | UndefinedType = UNDEFINED,
    ) -> TriggerStateDescription:
        """Return TriggerStateDescription dict."""
        included = _included_state_desc(state)
        return {
            "included_state": included,
            "excluded_state": _excluded_state_desc(state),
            "others_state": (
                included
                if isinstance(others_state, UndefinedType)
                else _included_state_desc(others_state)
            ),
            "count": count,
        }

    tests = [
        # Pattern: entities start unset (state=None / removed) and approach
        # a target state via an "other" intermediate.
        # Sequence per (target, other) pair:
        #   None -> target (0) -> other (0) -> target (1 or 0).
        # The first (target, 0) verifies that arming-from-None does not fire
        # on its own. The transition to `other` lets the trigger relax. The
        # final transition to `target` should fire — count is 1 by default,
        # but 0 when the trigger cannot fire from a None initial state (see
        # `trigger_from_none`).
        (
            trigger,
            trigger_options,
            list(
                itertools.chain.from_iterable(
                    (
                        state_with_attributes(None, 0),
                        state_with_attributes(target_state, 0),
                        state_with_attributes(other_state, 0),
                        state_with_attributes(
                            target_state, 1 if trigger_from_none else 0
                        ),
                    )
                    for target_state in target_states
                    for other_state in other_states
                )
            ),
        ),
        # Pattern: entities start in a non-target "other" state and toggle
        # back and forth to a target state.
        # Sequence per (target, other) pair:
        #   other -> target (1) -> other (0) -> target (1).
        # Verifies the trigger fires on each fresh other -> target
        # transition and does not fire on the reverse target -> other.
        (
            trigger,
            trigger_options,
            list(
                itertools.chain.from_iterable(
                    (
                        state_with_attributes(other_state, 0),
                        state_with_attributes(target_state, 1),
                        state_with_attributes(other_state, 0),
                        state_with_attributes(target_state, 1),
                    )
                    for target_state in target_states
                    for other_state in other_states
                )
            ),
        ),
        # Pattern: entities start *already* in the target state — the
        # trigger should not fire just because we arm against an already-
        # matching state — and we then exercise re-entry.
        # Sequence per (target, other) pair:
        #   target -> target (0, no-op)
        #          -> other  (0)
        #          -> target (1, fires on fresh other -> target)
        #          -> target (0, repeated target should not retrigger)
        #          -> unavailable (0).
        (
            trigger,
            trigger_options,
            list(
                itertools.chain.from_iterable(
                    (
                        state_with_attributes(target_state, 0),
                        state_with_attributes(target_state, 0),
                        state_with_attributes(other_state, 0),
                        state_with_attributes(target_state, 1),
                        # Repeat target state to test retriggering
                        state_with_attributes(target_state, 0),
                        state_with_attributes(STATE_UNAVAILABLE, 0),
                    )
                    for target_state in target_states
                    for other_state in other_states
                )
            ),
        ),
        # Pattern: an "other" -> "invalid" -> "other" round-trip should not
        # arm the trigger; only the subsequent other -> target transition
        # fires. Iterates `invalid_states` so unavailable/unknown plus any
        # caller-supplied extra invalids are all covered.
        # Sequence per (invalid, target, other):
        #   other -> invalid (0) -> other (0) -> target (1).
        (
            trigger,
            trigger_options,
            list(
                itertools.chain.from_iterable(
                    (
                        state_with_attributes(other_state, 0),
                        state_with_attributes(invalid_state, 0),
                        state_with_attributes(other_state, 0),
                        state_with_attributes(target_state, 1),
                    )
                    for invalid_state in invalid_states
                    for target_state in target_states
                    for other_state in other_states
                )
            ),
        ),
        # Pattern: entities start in an invalid state and recover. Mirrors
        # the previous pattern but with the invalid state as the *initial*
        # condition (so no transition out of it has occurred yet at arm
        # time). Iterates `invalid_states`.
        # Sequence per (invalid, target, other):
        #   invalid -> target (0) -> other (0) -> target (1).
        # The first target hop is 0 because the trigger doesn't fire when
        # arming-from-invalid is the very first transition.
        (
            trigger,
            trigger_options,
            list(
                itertools.chain.from_iterable(
                    (
                        state_with_attributes(invalid_state, 0),
                        state_with_attributes(target_state, 0),
                        state_with_attributes(other_state, 0),
                        state_with_attributes(target_state, 1),
                    )
                    for invalid_state in invalid_states
                    for target_state in target_states
                    for other_state in other_states
                )
            ),
        ),
    ]

    if len(target_states) > 1:
        # Pattern: transitions *between* distinct target states. For each
        # adjacent pair `(prev_target, target)` we verify that:
        # - prev_target -> target either retriggers or not, depending on
        #   `retrigger_on_target_state`,
        # - target -> other -> prev_target retriggers,
        # - prev_target -> target again obeys the retrigger flag,
        # - and a trailing target -> unavailable does not fire.
        # Sequence per (prev_target, target, other):
        #   prev_target
        #     -> target      (1 if retrigger_on_target_state else 0)
        #     -> other       (0)
        #     -> prev_target (1)
        #     -> target      (1 if retrigger_on_target_state else 0)
        #     -> unavailable (0).
        tests.append(
            (
                trigger,
                trigger_options,
                list(
                    itertools.chain.from_iterable(
                        (
                            state_with_attributes(target_states[idx - 1], 0),
                            state_with_attributes(
                                target_state, 1 if retrigger_on_target_state else 0
                            ),
                            state_with_attributes(other_state, 0),
                            state_with_attributes(target_states[idx - 1], 1),
                            state_with_attributes(
                                target_state, 1 if retrigger_on_target_state else 0
                            ),
                            state_with_attributes(STATE_UNAVAILABLE, 0),
                        )
                        for idx, target_state in enumerate(target_states[1:], start=1)
                        for other_state in other_states
                    )
                ),
            ),
        )

    # Pattern: the OTHER targeted entities sit in a state filtered by the
    # trigger's `_should_include` (default impl filters
    # missing/unavailable/unknown; overrides may add more, supplied by the
    # caller via `extra_excluded_states`). They are invisible to the
    # all/count checks, so even though they never enter `target_state` the
    # trigger should still fire when the entity under test alone transitions
    # other -> target.
    # Sequence per (target, other, excluded):
    #   step 0: all entities at `other`.
    #   step 1: entity_id stays at `other`, peers transition to `excluded`.
    #           This positions peers in their filtered state *before* the
    #           entity under test transitions, so all three behaviors
    #           (any/first/last) evaluate the firing transition with peers
    #           already filtered. count = 0.
    #   step 2: entity_id transitions to `target`, peers stay at `excluded`.
    #           The all/count check filters the peers out, so a single
    #           matching entity is enough to fire. count = 1.
    tests.append(
        (
            trigger,
            trigger_options,
            list(
                itertools.chain.from_iterable(
                    (
                        state_with_attributes(other_state, 0),
                        state_with_attributes(
                            other_state, 0, others_state=excluded_state
                        ),
                        state_with_attributes(
                            target_state, 1, others_state=excluded_state
                        ),
                    )
                    for target_state in target_states
                    for other_state in other_states
                    for excluded_state in excluded_states
                )
            ),
        )
    )

    return tests


def _add_threshold_unit(
    options: dict[str, Any], threshold_unit: str | None | UndefinedType
) -> dict[str, Any]:
    """Add unit to trigger thresholds if threshold_unit is provided."""
    if threshold_unit is UNDEFINED:
        return options
    options = copy.deepcopy(options)
    threshold_options = options["threshold"]
    for key in ("value", "value_min", "value_max"):
        if key not in threshold_options:
            continue
        threshold_options[key]["unit_of_measurement"] = threshold_unit
    return options


def parametrize_numerical_attribute_changed_trigger_states(
    trigger: str,
    state: str,
    attribute: str,
    *,
    threshold_unit: str | None | UndefinedType = UNDEFINED,
    trigger_options: dict[str, Any] | None = None,
    required_filter_attributes: dict | None = None,
    unit_attributes: dict | None = None,
    attribute_value_scale: float = 1.0,
    attribute_required: bool = False,
) -> list[tuple[str, dict[str, Any], list[TriggerStateDescription]]]:
    """Parametrize states for numerical-changed triggers.

    Generates state sequences for a trigger that fires whenever an attribute
    crosses or matches a "changed" threshold (modes "any" / "above" / "below").
    The trigger is exercised across three threshold types in turn; for each,
    the helper invokes `parametrize_trigger_states` with target/other/excluded
    states populated from the supplied `attribute` values. Threshold values
    are fixed at 10 and 90 (interpreted in the trigger's threshold unit).

    Returns a list of `(trigger, trigger_options, states)` tuples — the same
    shape as `parametrize_trigger_states`, suitable for splatting into a
    `pytest.mark.parametrize` over `("trigger", "trigger_options", "states")`.

    Args:
        trigger: Trigger key, e.g. `"climate.target_humidity_changed"`.
        state: The `state.state` value to use for entities meant to match the
            trigger (the attribute lives on top of this state).
        attribute: Name of the attribute the trigger reads. The helper
            generates target/other/excluded states by varying this attribute.
        threshold_unit: When set, the threshold values in `trigger_options`
            get this unit attached (`unit_of_measurement`). Defaults to
            UNDEFINED, meaning no unit is added.
        trigger_options: Extra keys merged into the generated `options` dict
            for each threshold-type variant.
        required_filter_attributes: Attributes that must be present on the
            entity for the trigger's domain filter to accept it (forwarded to
            `parametrize_trigger_states`). Use this for triggers gated by
            `device_class` or similar.
        unit_attributes: Attributes (typically `{ATTR_UNIT_OF_MEASUREMENT: ...}`)
            merged into every generated state, so the entity carries a unit
            alongside its tracked attribute.
        attribute_value_scale: Multiplier applied to the helper's fixed
            attribute values before they are written to the state. Use
            this when the trigger stores its tracked value on a different
            scale than the threshold — e.g. `media_player` volume is
            stored as 0.0-1.0 but the threshold is in percent, so pass
            `attribute_value_scale=0.01`.
        attribute_required: When True, `(state, {attribute: None})` is
            classified as an *excluded* state (filtered out of the all/count
            check by the trigger's `_should_include` override) instead of an
            "other" state. Set this for triggers that override
            `_should_include` to skip entities lacking the attribute.
    """
    trigger_options = trigger_options or {}
    unit_attributes = unit_attributes or {}
    # When `attribute_required=True`, `(attr=None)` is filtered by the
    # trigger's `_should_include` override, so it can no longer play the
    # role of a "non-firing but counted" other state. Substitute a
    # non-numeric string value: it fails `float(...)` (so is_valid_state is
    # False) but is still `is not None` (so the override includes it in
    # the all/count check), giving us a proper "other" state. Mirrors how
    # `parametrize_numerical_state_value_changed_trigger_states` uses the
    # literal string "none" as a non-numeric state value.
    s = attribute_value_scale
    if attribute_required:
        extra_excluded_states = [(state, {attribute: None} | unit_attributes)]
        other_invalid_attr = (state, {attribute: "none"} | unit_attributes)
    else:
        extra_excluded_states = None
        other_invalid_attr = (state, {attribute: None} | unit_attributes)

    return [
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options=_add_threshold_unit(
                {
                    "threshold": {
                        "type": "any",
                    },
                    **trigger_options,
                },
                threshold_unit,
            ),
            target_states=[
                (state, {attribute: 0 * s} | unit_attributes),
                (state, {attribute: 50 * s} | unit_attributes),
                (state, {attribute: 100 * s} | unit_attributes),
            ],
            other_states=[other_invalid_attr],
            extra_excluded_states=extra_excluded_states,
            required_filter_attributes=required_filter_attributes,
            retrigger_on_target_state=True,
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options=_add_threshold_unit(
                {
                    "threshold": {
                        "type": "above",
                        "value": {"number": 10},
                    },
                    **trigger_options,
                },
                threshold_unit,
            ),
            target_states=[
                (state, {attribute: 50 * s} | unit_attributes),
                (state, {attribute: 100 * s} | unit_attributes),
            ],
            other_states=[
                other_invalid_attr,
                (state, {attribute: 0 * s} | unit_attributes),
            ],
            extra_excluded_states=extra_excluded_states,
            required_filter_attributes=required_filter_attributes,
            retrigger_on_target_state=True,
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options=_add_threshold_unit(
                {
                    "threshold": {
                        "type": "below",
                        "value": {"number": 90},
                    },
                    **trigger_options,
                },
                threshold_unit,
            ),
            target_states=[
                (state, {attribute: 0 * s} | unit_attributes),
                (state, {attribute: 50 * s} | unit_attributes),
            ],
            other_states=[
                other_invalid_attr,
                (state, {attribute: 100 * s} | unit_attributes),
            ],
            extra_excluded_states=extra_excluded_states,
            required_filter_attributes=required_filter_attributes,
            retrigger_on_target_state=True,
        ),
    ]


def parametrize_numerical_attribute_crossed_threshold_trigger_states(
    trigger: str,
    state: str,
    attribute: str,
    *,
    threshold_unit: str | None | UndefinedType = UNDEFINED,
    trigger_options: dict[str, Any] | None = None,
    required_filter_attributes: dict | None = None,
    unit_attributes: dict | None = None,
    attribute_value_scale: float = 1.0,
    attribute_required: bool = False,
) -> list[tuple[str, dict[str, Any], list[TriggerStateDescription]]]:
    """Parametrize states for numerical crossed-threshold triggers.

    Generates state sequences for a trigger that fires when an attribute
    crosses a threshold boundary. The trigger is exercised across four
    threshold types in turn — "between", "outside", "above", and "below" —
    and for each, the helper invokes `parametrize_trigger_states` with
    target/other/excluded states populated from the supplied `attribute`
    values. Threshold values are fixed at 10 and 90 (or the pair (10, 90) for
    range modes), interpreted in the trigger's threshold unit.

    Returns a list of `(trigger, trigger_options, states)` tuples — the same
    shape as `parametrize_trigger_states`, suitable for splatting into a
    `pytest.mark.parametrize` over `("trigger", "trigger_options", "states")`.

    Args:
        trigger: Trigger key, e.g.
            `"climate.target_humidity_crossed_threshold"`.
        state: The `state.state` value to use for entities meant to match the
            trigger (the attribute lives on top of this state).
        attribute: Name of the attribute the trigger reads. The helper
            generates target/other/excluded states by varying this attribute.
        threshold_unit: When set, the threshold values in `trigger_options`
            get this unit attached (`unit_of_measurement`). Defaults to
            UNDEFINED, meaning no unit is added.
        trigger_options: Extra keys merged into the generated `options` dict
            for each threshold-type variant.
        required_filter_attributes: Attributes that must be present on the
            entity for the trigger's domain filter to accept it (forwarded to
            `parametrize_trigger_states`). Use this for triggers gated by
            `device_class` or similar.
        unit_attributes: Attributes (typically `{ATTR_UNIT_OF_MEASUREMENT: ...}`)
            merged into every generated state, so the entity carries a unit
            alongside its tracked attribute.
        attribute_value_scale: Multiplier applied to the helper's fixed
            attribute values before they are written to the state. Use
            this when the trigger stores its tracked value on a different
            scale than the threshold — e.g. `media_player` volume is
            stored as 0.0-1.0 but the threshold is in percent, so pass
            `attribute_value_scale=0.01`.
        attribute_required: When True, `(state, {attribute: None})` is
            classified as an *excluded* state (filtered out of the all/count
            check by the trigger's `_should_include` override) instead of an
            "other" state. Set this for triggers that override
            `_should_include` to skip entities lacking the attribute.
    """
    trigger_options = trigger_options or {}
    unit_attributes = unit_attributes or {}
    # See `parametrize_numerical_attribute_changed_trigger_states` for the
    # rationale of substituting a non-numeric string-attr for `(attr=None)`
    # when `attribute_required=True`: the override would filter `None`
    # out of the all/count check, so we use a value that fails
    # `is_valid_state` but is still included.
    s = attribute_value_scale
    if attribute_required:
        extra_excluded_states = [(state, {attribute: None} | unit_attributes)]
        other_invalid_attr = (state, {attribute: "none"} | unit_attributes)
    else:
        extra_excluded_states = None
        other_invalid_attr = (state, {attribute: None} | unit_attributes)

    return [
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options=_add_threshold_unit(
                {
                    "threshold": {
                        "type": "between",
                        "value_min": {"number": 10},
                        "value_max": {"number": 90},
                    },
                    **trigger_options,
                },
                threshold_unit,
            ),
            target_states=[
                (state, {attribute: 10 * s} | unit_attributes),
                (state, {attribute: 90 * s} | unit_attributes),
            ],
            other_states=[
                other_invalid_attr,
                (state, {attribute: 0 * s} | unit_attributes),
                (state, {attribute: 100 * s} | unit_attributes),
            ],
            extra_excluded_states=extra_excluded_states,
            required_filter_attributes=required_filter_attributes,
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options=_add_threshold_unit(
                {
                    "threshold": {
                        "type": "outside",
                        "value_min": {"number": 10},
                        "value_max": {"number": 90},
                    },
                    **trigger_options,
                },
                threshold_unit,
            ),
            target_states=[
                (state, {attribute: 0 * s} | unit_attributes),
                (state, {attribute: 100 * s} | unit_attributes),
            ],
            other_states=[
                other_invalid_attr,
                (state, {attribute: 10 * s} | unit_attributes),
                (state, {attribute: 90 * s} | unit_attributes),
            ],
            extra_excluded_states=extra_excluded_states,
            required_filter_attributes=required_filter_attributes,
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options=_add_threshold_unit(
                {
                    "threshold": {
                        "type": "above",
                        "value": {"number": 10},
                    },
                    **trigger_options,
                },
                threshold_unit,
            ),
            target_states=[
                (state, {attribute: 50 * s} | unit_attributes),
                (state, {attribute: 100 * s} | unit_attributes),
            ],
            other_states=[
                other_invalid_attr,
                (state, {attribute: 0 * s} | unit_attributes),
            ],
            extra_excluded_states=extra_excluded_states,
            required_filter_attributes=required_filter_attributes,
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options=_add_threshold_unit(
                {
                    "threshold": {
                        "type": "below",
                        "value": {"number": 90},
                    },
                    **trigger_options,
                },
                threshold_unit,
            ),
            target_states=[
                (state, {attribute: 0 * s} | unit_attributes),
                (state, {attribute: 50 * s} | unit_attributes),
            ],
            other_states=[
                other_invalid_attr,
                (state, {attribute: 100 * s} | unit_attributes),
            ],
            extra_excluded_states=extra_excluded_states,
            required_filter_attributes=required_filter_attributes,
        ),
    ]


def parametrize_numerical_state_value_changed_trigger_states(
    trigger: str,
    *,
    device_class: str,
    threshold_unit: str | None | UndefinedType = UNDEFINED,
    trigger_options: dict[str, Any] | None = None,
    unit_attributes: dict | None = None,
) -> list[tuple[str, dict[str, Any], list[TriggerStateDescription]]]:
    """Parametrize states for numerical state-value changed triggers.

    Unlike parametrize_numerical_attribute_changed_trigger_states,
    this is for entities where the tracked numerical value is in
    state.state (e.g. sensor entities), not in an attribute.
    """
    from homeassistant.const import ATTR_DEVICE_CLASS  # noqa: PLC0415

    required_filter_attributes = {ATTR_DEVICE_CLASS: device_class}
    trigger_options = trigger_options or {}
    unit_attributes = unit_attributes or {}

    return [
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options=_add_threshold_unit(
                {
                    "threshold": {
                        "type": "any",
                    },
                    **trigger_options,
                },
                threshold_unit,
            ),
            target_states=[
                ("0", unit_attributes),
                ("50", unit_attributes),
                ("100", unit_attributes),
            ],
            other_states=[("none", unit_attributes)],
            required_filter_attributes=required_filter_attributes,
            retrigger_on_target_state=True,
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options=_add_threshold_unit(
                {
                    "threshold": {
                        "type": "above",
                        "value": {"number": 10},
                    }
                }
                | trigger_options,
                threshold_unit,
            ),
            target_states=[("50", unit_attributes), ("100", unit_attributes)],
            other_states=[("none", unit_attributes), ("0", unit_attributes)],
            required_filter_attributes=required_filter_attributes,
            retrigger_on_target_state=True,
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options=_add_threshold_unit(
                {
                    "threshold": {
                        "type": "below",
                        "value": {"number": 90},
                    }
                }
                | trigger_options,
                threshold_unit,
            ),
            target_states=[("0", unit_attributes), ("50", unit_attributes)],
            other_states=[("none", unit_attributes), ("100", unit_attributes)],
            required_filter_attributes=required_filter_attributes,
            retrigger_on_target_state=True,
            trigger_from_none=False,
        ),
    ]


def parametrize_numerical_state_value_crossed_threshold_trigger_states(
    trigger: str,
    *,
    device_class: str,
    threshold_unit: str | None | UndefinedType = UNDEFINED,
    trigger_options: dict[str, Any] | None = None,
    unit_attributes: dict | None = None,
) -> list[tuple[str, dict[str, Any], list[TriggerStateDescription]]]:
    """Parametrize states for numerical state-value crossed threshold triggers.

    Unlike parametrize_numerical_attribute_crossed_threshold_trigger_states,
    this is for entities where the tracked numerical value is in state.state
    (e.g. sensor entities), not in an attribute.
    """
    from homeassistant.const import ATTR_DEVICE_CLASS  # noqa: PLC0415

    required_filter_attributes = {ATTR_DEVICE_CLASS: device_class}
    trigger_options = trigger_options or {}
    unit_attributes = unit_attributes or {}

    return [
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options=_add_threshold_unit(
                {
                    "threshold": {
                        "type": "between",
                        "value_min": {"number": 10},
                        "value_max": {"number": 90},
                    },
                    **trigger_options,
                },
                threshold_unit,
            ),
            target_states=[("10", unit_attributes), ("90", unit_attributes)],
            other_states=[
                ("none", unit_attributes),
                ("0", unit_attributes),
                ("100", unit_attributes),
            ],
            required_filter_attributes=required_filter_attributes,
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options=_add_threshold_unit(
                {
                    "threshold": {
                        "type": "outside",
                        "value_min": {"number": 10},
                        "value_max": {"number": 90},
                    },
                    **trigger_options,
                },
                threshold_unit,
            ),
            target_states=[("0", unit_attributes), ("100", unit_attributes)],
            other_states=[
                ("none", unit_attributes),
                ("10", unit_attributes),
                ("90", unit_attributes),
            ],
            required_filter_attributes=required_filter_attributes,
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options=_add_threshold_unit(
                {
                    "threshold": {
                        "type": "above",
                        "value": {"number": 10},
                    },
                    **trigger_options,
                },
                threshold_unit,
            ),
            target_states=[("50", unit_attributes), ("100", unit_attributes)],
            other_states=[("none", unit_attributes), ("0", unit_attributes)],
            required_filter_attributes=required_filter_attributes,
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options=_add_threshold_unit(
                {
                    "threshold": {
                        "type": "below",
                        "value": {"number": 90},
                    },
                    **trigger_options,
                },
                threshold_unit,
            ),
            target_states=[("0", unit_attributes), ("50", unit_attributes)],
            other_states=[("none", unit_attributes), ("100", unit_attributes)],
            required_filter_attributes=required_filter_attributes,
            trigger_from_none=False,
        ),
    ]


async def arm_trigger(
    hass: HomeAssistant,
    trigger: str,
    trigger_options: dict[str, Any] | None,
    trigger_target: dict,
    calls: list[str],
) -> None:
    """Arm the trigger and record fired entity_ids in calls."""
    options = {CONF_OPTIONS: {**trigger_options}} if trigger_options is not None else {}

    trigger_config = {
        CONF_PLATFORM: trigger,
        CONF_TARGET: {**trigger_target},
    } | options

    @callback
    def action(run_variables: TemplateVarsType, context: Context | None = None) -> None:
        calls.append(run_variables["trigger"]["entity_id"])

    logger = logging.getLogger(__name__)

    def log_cb(level: int, msg: str, **kwargs: Any) -> None:
        logger._log(level, "%s", msg, **kwargs)

    validated_config = await async_validate_trigger_config(hass, [trigger_config])
    await async_initialize_triggers(
        hass,
        validated_config,
        action,
        domain="test",
        name="test_trigger",
        log_cb=log_cb,
    )


async def create_target_condition(
    hass: HomeAssistant,
    *,
    condition: str,
    target: dict,
    behavior: str,
    condition_options: dict[str, Any] | None = None,
) -> ConditionCheckerTypeOptional:
    """Create a target condition."""
    validated_config = await async_validate_condition_config(
        hass,
        {
            CONF_CONDITION: condition,
            CONF_TARGET: target,
            CONF_OPTIONS: {"behavior": behavior, **(condition_options or {})},
        },
    )
    return await async_condition_from_config(hass, validated_config)


def set_or_remove_state(
    hass: HomeAssistant,
    entity_id: str,
    state: StateDescription,
) -> None:
    """Set or remove the state of an entity."""
    if state["state"] is None:
        hass.states.async_remove(entity_id)
    else:
        hass.states.async_set(
            entity_id, state["state"], state["attributes"], force_update=True
        )


def other_states(state: StrEnum | Iterable[StrEnum]) -> list[str]:
    """Return a sorted list with all states except the specified one."""
    if isinstance(state, StrEnum):
        excluded_values = {state.value}
        enum_class = state.__class__
    else:
        if len(state) == 0:
            raise ValueError("state iterable must not be empty")
        excluded_values = {s.value for s in state}
        enum_class = list(state)[0].__class__

    return sorted({s.value for s in enum_class} - excluded_values)


async def _validate_condition_options(
    hass: HomeAssistant,
    condition: str,
    options: dict[str, Any] | None,
    *,
    valid: bool,
    supports_target: bool = True,
) -> None:
    """Assert that a condition accepts or rejects the given options."""
    config: dict[str, Any] = {CONF_CONDITION: condition}
    if supports_target:
        config[CONF_TARGET] = {ATTR_LABEL_ID: "test_label"}
    if options is not None:
        config[CONF_OPTIONS] = options
    if valid:
        await async_validate_condition_config(hass, config)
    else:
        with pytest.raises(vol.Invalid):
            await async_validate_condition_config(hass, config)


def _get_yaml_fields(automation_key: str, yaml_type: str) -> dict[str, Any]:
    """Load a conditions.yaml or triggers.yaml and return the fields for a key."""
    domain, key = automation_key.split(".", 1)
    yaml_path = (
        Path(__file__).parents[2]
        / "homeassistant"
        / "components"
        / domain
        / f"{yaml_type}.yaml"
    )
    data = load_yaml_dict(str(yaml_path))
    # YAML anchors (keys starting with '.') are included in the parsed dict;
    # the actual entry uses the plain key name.
    entry = data.get(key, {})
    return entry.get("fields", {})


def _assert_yaml_has_field(
    yaml_file: str, automation_key: str, field: str, *, expected: bool
) -> None:
    """Assert that a field is present or absent in a yaml description."""
    yaml_fields = _get_yaml_fields(automation_key, yaml_file)
    has_field = field in yaml_fields
    assert has_field == expected, (
        f"{automation_key}: {yaml_file}.yaml {'has' if has_field else 'is missing'}"
        f" '{field}', but expected {expected}"
    )


async def assert_condition_options_supported(
    hass: HomeAssistant,
    condition: str,
    base_options: dict[str, Any] | None,
    *,
    supports_behavior: bool,
    supports_duration: bool,
    supports_target: bool = True,
) -> None:
    """Assert which options a condition supports.

    Tests that the condition:
    - Accepts the minimal config (base_options)
    - Accepts/rejects behavior depending on supports_behavior
    - Accepts/rejects duration depending on supports_duration
    - Rejects unknown options
    - Condition yaml description matches supports_behavior / supports_duration
    """
    # Verify that the yaml description matches the flags
    _assert_yaml_has_field(
        "conditions", condition, "behavior", expected=supports_behavior
    )
    _assert_yaml_has_field("conditions", condition, "for", expected=supports_duration)

    # Minimal config should always be valid
    # If there are no base options, also test that options can be omitted or be empty
    supports_empty = not bool(base_options)
    await _validate_condition_options(
        hass, condition, None, valid=supports_empty, supports_target=supports_target
    )
    await _validate_condition_options(
        hass, condition, {}, valid=supports_empty, supports_target=supports_target
    )
    await _validate_condition_options(
        hass, condition, base_options, valid=True, supports_target=supports_target
    )

    def _merge(extra: dict[str, Any]) -> dict[str, Any]:
        return {**(base_options or {}), **extra}

    # Behavior
    for behavior in ("any", "all"):
        await _validate_condition_options(
            hass,
            condition,
            _merge({"behavior": behavior}),
            valid=supports_behavior,
            supports_target=supports_target,
        )

    # Duration
    for for_value in ({"seconds": 5}, "00:00:05", 5):
        await _validate_condition_options(
            hass,
            condition,
            _merge({"for": for_value}),
            valid=supports_duration,
            supports_target=supports_target,
        )

    # Unknown option should always be rejected
    await _validate_condition_options(
        hass,
        condition,
        _merge({"unknown_option": True}),
        valid=False,
        supports_target=supports_target,
    )


async def _validate_trigger_options(
    hass: HomeAssistant,
    trigger: str,
    options: dict[str, Any] | None,
    *,
    valid: bool,
    supports_target: bool = True,
) -> None:
    """Assert that a trigger accepts or rejects the given options during validation."""
    trigger_config: dict[str, Any] = {CONF_PLATFORM: trigger}
    if supports_target:
        trigger_config[CONF_TARGET] = {ATTR_LABEL_ID: "test_label"}
    if options is not None:
        trigger_config[CONF_OPTIONS] = options
    if valid:
        await async_validate_trigger_config(hass, [trigger_config])
    else:
        with pytest.raises(vol.Invalid):
            await async_validate_trigger_config(hass, [trigger_config])


async def assert_trigger_options_supported(
    hass: HomeAssistant,
    trigger: str,
    base_options: dict[str, Any] | None,
    *,
    supports_behavior: bool,
    supports_duration: bool,
    supports_target: bool = True,
) -> None:
    """Assert which options a trigger supports.

    Tests that the trigger:
    - Accepts the minimal config (base_options)
    - Accepts/rejects behavior depending on supports_behavior
    - Accepts/rejects duration depending on supports_duration
    - Rejects unknown options
    - Trigger yaml description matches supports_behavior / supports_duration
    """
    # Verify that the yaml description matches the flags
    _assert_yaml_has_field("triggers", trigger, "behavior", expected=supports_behavior)
    _assert_yaml_has_field("triggers", trigger, "for", expected=supports_duration)

    # Minimal config should always be valid
    supports_empty = not bool(base_options)
    await _validate_trigger_options(
        hass, trigger, None, valid=supports_empty, supports_target=supports_target
    )
    await _validate_trigger_options(
        hass, trigger, {}, valid=supports_empty, supports_target=supports_target
    )
    await _validate_trigger_options(
        hass, trigger, base_options, valid=True, supports_target=supports_target
    )

    def _merge(extra: dict[str, Any]) -> dict[str, Any]:
        return {**(base_options or {}), **extra}

    # Behavior
    for behavior in ("each", "first", "all"):
        await _validate_trigger_options(
            hass,
            trigger,
            _merge({"behavior": behavior}),
            valid=supports_behavior,
            supports_target=supports_target,
        )

    # Duration
    for for_value in ({"seconds": 5}, "00:00:05", 5):
        await _validate_trigger_options(
            hass,
            trigger,
            _merge({"for": for_value}),
            valid=supports_duration,
            supports_target=supports_target,
        )

    # Unknown option should always be rejected
    await _validate_trigger_options(
        hass,
        trigger,
        _merge({"unknown_option": True}),
        valid=False,
        supports_target=supports_target,
    )


async def assert_condition_behavior_any(
    hass: HomeAssistant,
    *,
    target_entities: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test condition with the 'any' behavior."""
    other_entity_ids = set(target_entities["included_entities"]) - {entity_id}
    excluded_entity_ids = set(target_entities["excluded_entities"]) - {entity_id}

    for eid in target_entities["included_entities"]:
        set_or_remove_state(hass, eid, states[0]["included_state"])
        await hass.async_block_till_done()
    for eid in excluded_entity_ids:
        set_or_remove_state(hass, eid, states[0]["excluded_state"])
        await hass.async_block_till_done()

    cond = await create_target_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="any",
        condition_options=condition_options,
    )

    for state in states:
        included_state = state["included_state"]
        excluded_state = state["excluded_state"]

        # Set excluded entities first to verify that they don't make the
        # condition evaluate to true
        for excluded_entity_id in excluded_entity_ids:
            set_or_remove_state(hass, excluded_entity_id, excluded_state)
            await hass.async_block_till_done()
        assert cond.async_check() is False

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert cond.async_check() == state["condition_true"]

        # Set other included entities to the included state to verify that
        # they don't change the condition evaluation
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert cond.async_check() == state["condition_true"]


async def assert_condition_behavior_all(
    hass: HomeAssistant,
    *,
    target_entities: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test condition with the 'all' behavior."""
    other_entity_ids = set(target_entities["included_entities"]) - {entity_id}
    excluded_entity_ids = set(target_entities["excluded_entities"]) - {entity_id}

    for eid in target_entities["included_entities"]:
        set_or_remove_state(hass, eid, states[0]["included_state"])
        await hass.async_block_till_done()
    for eid in excluded_entity_ids:
        set_or_remove_state(hass, eid, states[0]["excluded_state"])
        await hass.async_block_till_done()

    cond = await create_target_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="all",
        condition_options=condition_options,
    )

    for state in states:
        included_state = state["included_state"]
        excluded_state = state["excluded_state"]

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert cond.async_check() == state["condition_true_first_entity"]

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        for excluded_entity_id in excluded_entity_ids:
            set_or_remove_state(hass, excluded_entity_id, excluded_state)
            await hass.async_block_till_done()

        assert cond.async_check() == state["condition_true"]


async def assert_trigger_behavior_each(
    hass: HomeAssistant,
    *,
    target_entities: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test trigger fires in mode each."""
    calls: list[str] = []
    other_entity_ids = set(target_entities["included_entities"]) - {entity_id}
    excluded_entity_ids = set(target_entities["excluded_entities"]) - {entity_id}

    for eid in target_entities["included_entities"]:
        set_or_remove_state(hass, eid, states[0]["included_state"])
        await hass.async_block_till_done()
    for eid in excluded_entity_ids:
        set_or_remove_state(hass, eid, states[0]["excluded_state"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, trigger_options, trigger_target_config, calls)

    for state in states[1:]:
        excluded_state = state["excluded_state"]
        included_state = state["included_state"]
        others_state = state["others_state"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(calls) == state["count"]
        for call in calls:
            assert call == entity_id
        calls.clear()

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, others_state)
            await hass.async_block_till_done()
        for excluded_entity_id in excluded_entity_ids:
            set_or_remove_state(hass, excluded_entity_id, excluded_state)
            await hass.async_block_till_done()
        # When others_state differs from included_state, the post-others count
        # is 0: others are placed in a state filtered or rejected by the
        # trigger, so they don't fire individually.
        expected_others_count = (
            (entities_in_target - 1) * state["count"]
            if others_state == included_state
            else 0
        )
        assert len(calls) == expected_others_count
        calls.clear()


async def assert_trigger_behavior_first(
    hass: HomeAssistant,
    *,
    target_entities: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test trigger fires in mode first."""
    calls: list[str] = []
    other_entity_ids = set(target_entities["included_entities"]) - {entity_id}
    excluded_entity_ids = set(target_entities["excluded_entities"]) - {entity_id}

    for eid in target_entities["included_entities"]:
        set_or_remove_state(hass, eid, states[0]["included_state"])
        await hass.async_block_till_done()
    for eid in excluded_entity_ids:
        set_or_remove_state(hass, eid, states[0]["excluded_state"])
        await hass.async_block_till_done()

    await arm_trigger(
        hass,
        trigger,
        {"behavior": "first"} | trigger_options,
        trigger_target_config,
        calls,
    )

    for state in states[1:]:
        excluded_state = state["excluded_state"]
        included_state = state["included_state"]
        others_state = state["others_state"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(calls) == state["count"]
        for call in calls:
            assert call == entity_id
        calls.clear()

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, others_state)
            await hass.async_block_till_done()
        for excluded_entity_id in excluded_entity_ids:
            set_or_remove_state(hass, excluded_entity_id, excluded_state)
            await hass.async_block_till_done()
        assert len(calls) == 0


async def assert_trigger_behavior_all(
    hass: HomeAssistant,
    *,
    target_entities: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test trigger fires in mode all."""
    calls: list[str] = []
    other_entity_ids = set(target_entities["included_entities"]) - {entity_id}
    excluded_entity_ids = set(target_entities["excluded_entities"]) - {entity_id}

    for eid in target_entities["included_entities"]:
        set_or_remove_state(hass, eid, states[0]["included_state"])
        await hass.async_block_till_done()
    for eid in excluded_entity_ids:
        set_or_remove_state(hass, eid, states[0]["excluded_state"])
        await hass.async_block_till_done()

    await arm_trigger(
        hass,
        trigger,
        {"behavior": "all"} | trigger_options,
        trigger_target_config,
        calls,
    )

    for state in states[1:]:
        excluded_state = state["excluded_state"]
        included_state = state["included_state"]
        others_state = state["others_state"]
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, others_state)
            await hass.async_block_till_done()
        assert len(calls) == 0

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(calls) == state["count"]
        for call in calls:
            assert call == entity_id
        calls.clear()

        for excluded_entity_id in excluded_entity_ids:
            set_or_remove_state(hass, excluded_entity_id, excluded_state)
            await hass.async_block_till_done()
        assert len(calls) == 0


def parametrize_numerical_condition_above_below_any(
    condition: str,
    *,
    device_class: str,
    condition_options: dict[str, Any] | None = None,
    threshold_unit: str | None | UndefinedType = UNDEFINED,
    unit_attributes: dict | None = None,
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize threshold cases for state-value numerical conditions.

    Uses behavior=any. Generates state sequences for a condition
    that reads its tracked value directly from `state.state`
    (e.g. a sensor with a temperature device
    class). The condition is exercised across three threshold types in turn
    — "above", "below", "between" — and for each, the helper invokes
    `parametrize_condition_states_any` with target/other states populated
    from a fixed set of numeric values straddling the thresholds.

    Threshold values are fixed at 20 / 80 (interpreted in the condition's
    threshold unit). The `device_class` filter is applied via
    `required_filter_attributes={ATTR_DEVICE_CLASS: device_class}` so
    entities outside that device class are ignored by the condition.

    Returns a list of `(condition, condition_options, states)` tuples,
    suitable for unpacking into a `pytest.mark.parametrize` over
    `("condition", "condition_options", "states")`.

    Args:
        condition: Condition key, e.g. `"temperature.is"`.
        device_class: Device class the condition filters on. Forwarded to
            `parametrize_condition_states_any` as
            `required_filter_attributes={ATTR_DEVICE_CLASS: device_class}`.
        condition_options: Extra keys merged into the generated `options`
            dict for each threshold-type variant (e.g. user-supplied
            condition-specific keys; the threshold itself is set by the
            helper).
        threshold_unit: When set, the threshold values in
            `condition_options` get this unit attached
            (`unit_of_measurement`). Defaults to UNDEFINED, meaning no unit
            is added.
        unit_attributes: Attributes (typically
            `{ATTR_UNIT_OF_MEASUREMENT: ...}`) merged into every generated
            state, so the entity carries a unit alongside its tracked
            value.
    """
    from homeassistant.const import ATTR_DEVICE_CLASS  # noqa: PLC0415

    required_filter_attributes = {ATTR_DEVICE_CLASS: device_class}
    condition_options = condition_options or {}
    unit_attributes = unit_attributes or {}

    return [
        *parametrize_condition_states_any(
            condition=condition,
            condition_options=_add_threshold_unit(
                {
                    "threshold": {"type": "above", "value": {"number": 20}},
                    **condition_options,
                },
                threshold_unit,
            ),
            target_states=[
                ("21", unit_attributes),
                ("50", unit_attributes),
                ("100", unit_attributes),
            ],
            other_states=[
                ("0", unit_attributes),
                ("10", unit_attributes),
                ("20", unit_attributes),
            ],
            required_filter_attributes=required_filter_attributes,
        ),
        *parametrize_condition_states_any(
            condition=condition,
            condition_options=_add_threshold_unit(
                {
                    "threshold": {"type": "below", "value": {"number": 80}},
                    **condition_options,
                },
                threshold_unit,
            ),
            target_states=[
                ("0", unit_attributes),
                ("50", unit_attributes),
                ("79", unit_attributes),
            ],
            other_states=[
                ("80", unit_attributes),
                ("90", unit_attributes),
                ("100", unit_attributes),
            ],
            required_filter_attributes=required_filter_attributes,
        ),
        *parametrize_condition_states_any(
            condition=condition,
            condition_options=_add_threshold_unit(
                {
                    "threshold": {
                        "type": "between",
                        "value_min": {"number": 20},
                        "value_max": {"number": 80},
                    },
                    **condition_options,
                },
                threshold_unit,
            ),
            target_states=[
                ("20", unit_attributes),
                ("50", unit_attributes),
                ("80", unit_attributes),
            ],
            other_states=[
                ("0", unit_attributes),
                ("19", unit_attributes),
                ("81", unit_attributes),
                ("100", unit_attributes),
            ],
            required_filter_attributes=required_filter_attributes,
        ),
    ]


def parametrize_numerical_condition_above_below_all(
    condition: str,
    *,
    device_class: str,
    condition_options: dict[str, Any] | None = None,
    threshold_unit: str | None | UndefinedType = UNDEFINED,
    unit_attributes: dict | None = None,
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize threshold cases for state-value numerical conditions.

    Uses behavior=all.

    See `parametrize_numerical_condition_above_below_any` for the structure
    of the generated test cases; the only difference is that this helper
    routes through `parametrize_condition_states_all`, so the condition is
    expected to evaluate True only when *every* targeted entity matches the
    threshold (vacuous-True when every entity is filtered out).

    Returns a list of `(condition, condition_options, states)` tuples,
    suitable for unpacking into a `pytest.mark.parametrize` over
    `("condition", "condition_options", "states")`.

    Args:
        condition: Condition key, e.g. `"temperature.is"`.
        device_class: Device class the condition filters on. Forwarded to
            `parametrize_condition_states_all` as
            `required_filter_attributes={ATTR_DEVICE_CLASS: device_class}`.
        condition_options: Extra keys merged into the generated `options`
            dict for each threshold-type variant (e.g. user-supplied
            condition-specific keys; the threshold itself is set by the
            helper).
        threshold_unit: When set, the threshold values in
            `condition_options` get this unit attached
            (`unit_of_measurement`). Defaults to UNDEFINED, meaning no unit
            is added.
        unit_attributes: Attributes (typically
            `{ATTR_UNIT_OF_MEASUREMENT: ...}`) merged into every generated
            state, so the entity carries a unit alongside its tracked
            value.
    """
    from homeassistant.const import ATTR_DEVICE_CLASS  # noqa: PLC0415

    required_filter_attributes = {ATTR_DEVICE_CLASS: device_class}
    condition_options = condition_options or {}
    unit_attributes = unit_attributes or {}

    return [
        *parametrize_condition_states_all(
            condition=condition,
            condition_options=_add_threshold_unit(
                {
                    "threshold": {"type": "above", "value": {"number": 20}},
                    **condition_options,
                },
                threshold_unit,
            ),
            target_states=[
                ("21", unit_attributes),
                ("50", unit_attributes),
                ("100", unit_attributes),
            ],
            other_states=[
                ("0", unit_attributes),
                ("10", unit_attributes),
                ("20", unit_attributes),
            ],
            required_filter_attributes=required_filter_attributes,
        ),
        *parametrize_condition_states_all(
            condition=condition,
            condition_options=_add_threshold_unit(
                {
                    "threshold": {"type": "below", "value": {"number": 80}},
                    **condition_options,
                },
                threshold_unit,
            ),
            target_states=[
                ("0", unit_attributes),
                ("50", unit_attributes),
                ("79", unit_attributes),
            ],
            other_states=[
                ("80", unit_attributes),
                ("90", unit_attributes),
                ("100", unit_attributes),
            ],
            required_filter_attributes=required_filter_attributes,
        ),
        *parametrize_condition_states_all(
            condition=condition,
            condition_options=_add_threshold_unit(
                {
                    "threshold": {
                        "type": "between",
                        "value_min": {"number": 20},
                        "value_max": {"number": 80},
                    },
                    **condition_options,
                },
                threshold_unit,
            ),
            target_states=[
                ("20", unit_attributes),
                ("50", unit_attributes),
                ("80", unit_attributes),
            ],
            other_states=[
                ("0", unit_attributes),
                ("19", unit_attributes),
                ("81", unit_attributes),
                ("100", unit_attributes),
            ],
            required_filter_attributes=required_filter_attributes,
        ),
    ]


def parametrize_numerical_attribute_condition_above_below_any(
    condition: str,
    state: str,
    attribute: str,
    *,
    condition_options: dict[str, Any] | None = None,
    required_filter_attributes: dict | None = None,
    threshold_unit: str | None | UndefinedType = UNDEFINED,
    unit_attributes: dict | None = None,
    attribute_required: bool = False,
    attribute_value_scale: float = 1.0,
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize threshold cases for attribute-based numerical conditions.

    Uses behavior=any. Generates state sequences for a condition
    that reads its tracked value from a state attribute
    (e.g. `climate.is_target_humidity`). The condition
    is exercised across three threshold types in turn — "above", "below",
    "between" — and for each, the helper invokes
    `parametrize_condition_states_any` with target/other states populated
    from a fixed set of numeric attribute values straddling the
    thresholds. Threshold values are fixed at 20 / 80 (interpreted in the
    condition's threshold unit).

    Returns a list of `(condition, condition_options, states)` tuples,
    suitable for unpacking into a `pytest.mark.parametrize` over
    `("condition", "condition_options", "states")`.

    Args:
        condition: Condition key, e.g. `"climate.is_target_humidity"`.
        state: The `state.state` value to use for entities meant to match
            the condition (the attribute lives on top of this state).
        attribute: Name of the attribute the condition reads. The helper
            generates target/other/excluded states by varying this
            attribute.
        condition_options: Extra keys merged into the generated `options`
            dict for each threshold-type variant (the threshold itself is
            set by the helper).
        required_filter_attributes: Attributes that must be present on the
            entity for the condition's domain filter to accept it. The
            helper merges these into every generated state so the entity
            satisfies the filter; entities outside the target receive the
            same state value but *without* these attributes.
        threshold_unit: When set, the threshold values in
            `condition_options` get this unit attached
            (`unit_of_measurement`). Defaults to UNDEFINED, meaning no
            unit is added.
        unit_attributes: Attributes (typically
            `{ATTR_UNIT_OF_MEASUREMENT: ...}`) merged into every generated
            state, so the entity carries a unit alongside its tracked
            attribute.
        attribute_required: When True, `(state, {attribute: None})` is
            classified as an *excluded* state (filtered out of the all/any
            check by the condition's `_should_include` override) rather
            than treated as just-missing. Set this for conditions whose
            `_should_include` skips entities lacking the tracked
            attribute.
        attribute_value_scale: Multiplier applied to the helper's fixed
            attribute values before they are written to the state. Use
            this when the condition stores its tracked value on a
            different scale than the threshold — e.g. `media_player`
            volume is stored as 0.0-1.0 but the threshold is in percent,
            so pass `attribute_value_scale=0.01`; light brightness is
            stored as 0-255 but the threshold is in percent, so pass
            `attribute_value_scale=255/100`.
    """
    condition_options = condition_options or {}
    unit_attributes = unit_attributes or {}
    s = attribute_value_scale
    extra_excluded_states = (
        [(state, {attribute: None} | unit_attributes)] if attribute_required else None
    )

    return [
        *parametrize_condition_states_any(
            condition=condition,
            condition_options=_add_threshold_unit(
                {
                    "threshold": {"type": "above", "value": {"number": 20}},
                    **condition_options,
                },
                threshold_unit,
            ),
            target_states=[
                (state, {attribute: 21 * s} | unit_attributes),
                (state, {attribute: 50 * s} | unit_attributes),
                (state, {attribute: 100 * s} | unit_attributes),
            ],
            other_states=[
                (state, {attribute: 0 * s} | unit_attributes),
                (state, {attribute: 10 * s} | unit_attributes),
                (state, {attribute: 20 * s} | unit_attributes),
            ],
            extra_excluded_states=extra_excluded_states,
            required_filter_attributes=required_filter_attributes,
        ),
        *parametrize_condition_states_any(
            condition=condition,
            condition_options=_add_threshold_unit(
                {
                    "threshold": {"type": "below", "value": {"number": 80}},
                    **condition_options,
                },
                threshold_unit,
            ),
            target_states=[
                (state, {attribute: 0 * s} | unit_attributes),
                (state, {attribute: 50 * s} | unit_attributes),
                (state, {attribute: 79 * s} | unit_attributes),
            ],
            other_states=[
                (state, {attribute: 80 * s} | unit_attributes),
                (state, {attribute: 90 * s} | unit_attributes),
                (state, {attribute: 100 * s} | unit_attributes),
            ],
            extra_excluded_states=extra_excluded_states,
            required_filter_attributes=required_filter_attributes,
        ),
        *parametrize_condition_states_any(
            condition=condition,
            condition_options=_add_threshold_unit(
                {
                    "threshold": {
                        "type": "between",
                        "value_min": {"number": 20},
                        "value_max": {"number": 80},
                    },
                    **condition_options,
                },
                threshold_unit,
            ),
            target_states=[
                (state, {attribute: 20 * s} | unit_attributes),
                (state, {attribute: 50 * s} | unit_attributes),
                (state, {attribute: 80 * s} | unit_attributes),
            ],
            other_states=[
                (state, {attribute: 0 * s} | unit_attributes),
                (state, {attribute: 19 * s} | unit_attributes),
                (state, {attribute: 81 * s} | unit_attributes),
                (state, {attribute: 100 * s} | unit_attributes),
            ],
            extra_excluded_states=extra_excluded_states,
            required_filter_attributes=required_filter_attributes,
        ),
    ]


def parametrize_numerical_attribute_condition_above_below_all(
    condition: str,
    state: str,
    attribute: str,
    *,
    condition_options: dict[str, Any] | None = None,
    required_filter_attributes: dict | None = None,
    threshold_unit: str | None | UndefinedType = UNDEFINED,
    unit_attributes: dict | None = None,
    attribute_required: bool = False,
    attribute_value_scale: float = 1.0,
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize threshold cases for attribute-based numerical conditions.

    Uses behavior=all.

    See `parametrize_numerical_attribute_condition_above_below_any` for the
    structure of the generated test cases; the only difference is that this
    helper routes through `parametrize_condition_states_all`, so the
    condition is expected to evaluate True only when *every* targeted
    entity matches the threshold (vacuous-True when every entity is
    filtered out).

    Returns a list of `(condition, condition_options, states)` tuples,
    suitable for unpacking into a `pytest.mark.parametrize` over
    `("condition", "condition_options", "states")`.

    Args:
        condition: Condition key, e.g. `"climate.is_target_humidity"`.
        state: The `state.state` value to use for entities meant to match
            the condition (the attribute lives on top of this state).
        attribute: Name of the attribute the condition reads. The helper
            generates target/other/excluded states by varying this
            attribute.
        condition_options: Extra keys merged into the generated `options`
            dict for each threshold-type variant (the threshold itself is
            set by the helper).
        required_filter_attributes: Attributes that must be present on the
            entity for the condition's domain filter to accept it. The
            helper merges these into every generated state so the entity
            satisfies the filter; entities outside the target receive the
            same state value but *without* these attributes.
        threshold_unit: When set, the threshold values in
            `condition_options` get this unit attached
            (`unit_of_measurement`). Defaults to UNDEFINED, meaning no
            unit is added.
        unit_attributes: Attributes (typically
            `{ATTR_UNIT_OF_MEASUREMENT: ...}`) merged into every generated
            state, so the entity carries a unit alongside its tracked
            attribute.
        attribute_required: When True, `(state, {attribute: None})` is
            classified as an *excluded* state (filtered out of the all/any
            check by the condition's `_should_include` override) rather
            than treated as just-missing. Set this for conditions whose
            `_should_include` skips entities lacking the tracked
            attribute.
        attribute_value_scale: Multiplier applied to the helper's fixed
            attribute values before they are written to the state. Use
            this when the condition stores its tracked value on a
            different scale than the threshold — e.g. `media_player`
            volume is stored as 0.0-1.0 but the threshold is in percent,
            so pass `attribute_value_scale=0.01`; light brightness is
            stored as 0-255 but the threshold is in percent, so pass
            `attribute_value_scale=255/100`.
    """
    condition_options = condition_options or {}
    unit_attributes = unit_attributes or {}
    s = attribute_value_scale
    extra_excluded_states = (
        [(state, {attribute: None} | unit_attributes)] if attribute_required else None
    )

    return [
        *parametrize_condition_states_all(
            condition=condition,
            condition_options=_add_threshold_unit(
                {
                    "threshold": {"type": "above", "value": {"number": 20}},
                    **condition_options,
                },
                threshold_unit,
            ),
            target_states=[
                (state, {attribute: 21 * s} | unit_attributes),
                (state, {attribute: 50 * s} | unit_attributes),
                (state, {attribute: 100 * s} | unit_attributes),
            ],
            other_states=[
                (state, {attribute: 0 * s} | unit_attributes),
                (state, {attribute: 10 * s} | unit_attributes),
                (state, {attribute: 20 * s} | unit_attributes),
            ],
            extra_excluded_states=extra_excluded_states,
            required_filter_attributes=required_filter_attributes,
        ),
        *parametrize_condition_states_all(
            condition=condition,
            condition_options=_add_threshold_unit(
                {
                    "threshold": {"type": "below", "value": {"number": 80}},
                    **condition_options,
                },
                threshold_unit,
            ),
            target_states=[
                (state, {attribute: 0 * s} | unit_attributes),
                (state, {attribute: 50 * s} | unit_attributes),
                (state, {attribute: 79 * s} | unit_attributes),
            ],
            other_states=[
                (state, {attribute: 80 * s} | unit_attributes),
                (state, {attribute: 90 * s} | unit_attributes),
                (state, {attribute: 100 * s} | unit_attributes),
            ],
            extra_excluded_states=extra_excluded_states,
            required_filter_attributes=required_filter_attributes,
        ),
        *parametrize_condition_states_all(
            condition=condition,
            condition_options=_add_threshold_unit(
                {
                    "threshold": {
                        "type": "between",
                        "value_min": {"number": 20},
                        "value_max": {"number": 80},
                    },
                    **condition_options,
                },
                threshold_unit,
            ),
            target_states=[
                (state, {attribute: 20 * s} | unit_attributes),
                (state, {attribute: 50 * s} | unit_attributes),
                (state, {attribute: 80 * s} | unit_attributes),
            ],
            other_states=[
                (state, {attribute: 0 * s} | unit_attributes),
                (state, {attribute: 19 * s} | unit_attributes),
                (state, {attribute: 81 * s} | unit_attributes),
                (state, {attribute: 100 * s} | unit_attributes),
            ],
            extra_excluded_states=extra_excluded_states,
            required_filter_attributes=required_filter_attributes,
        ),
    ]


async def assert_trigger_ignores_limit_entities_with_wrong_unit(
    hass: HomeAssistant,
    *,
    trigger: str,
    trigger_options: dict[str, Any],
    entity_id: str,
    reset_state: StateDescription,
    trigger_state: StateDescription,
    limit_entities: list[tuple[str, str]],
    correct_unit: str,
    wrong_unit: str,
) -> None:
    """Test that a trigger does not fire when limit entities have the wrong unit.

    Verifies that ALL limit entities must have the correct unit_of_measurement
    for the trigger to fire. Limit entities are fixed one at a time; the trigger
    should only fire once all of them have the correct unit.

    Args:
        trigger: The trigger key (e.g. "light.brightness_crossed_threshold").
        trigger_options: Trigger options dict (must already contain the limit
            entity IDs as values).
        entity_id: The entity being observed by the trigger.
        reset_state: The state description for the reset phase.
        trigger_state: The state description that should cause the trigger to fire.
        limit_entities: List of (entity_id, value) tuples for the limit entities.
        correct_unit: The unit that the trigger expects (e.g. "%").
        wrong_unit: A unit that the trigger should reject (e.g. "lx").

    """
    calls: list[str] = []
    # Set up entity in triggering state
    set_or_remove_state(hass, entity_id, trigger_state)
    # Set up all limit entities with the wrong unit
    for limit_entity_id, limit_value in limit_entities:
        hass.states.async_set(
            limit_entity_id,
            limit_value,
            {ATTR_UNIT_OF_MEASUREMENT: wrong_unit},
        )
    await hass.async_block_till_done()

    await arm_trigger(
        hass, trigger, trigger_options, {CONF_ENTITY_ID: [entity_id]}, calls
    )

    # Cycle entity state - should NOT fire (all limit entities have wrong unit)
    set_or_remove_state(hass, entity_id, reset_state)
    await hass.async_block_till_done()
    set_or_remove_state(hass, entity_id, trigger_state)
    await hass.async_block_till_done()
    assert len(calls) == 0

    # Fix limit entities one at a time; trigger should not fire until all are fixed
    for i, (limit_entity_id, limit_value) in enumerate(limit_entities):
        hass.states.async_set(
            limit_entity_id,
            limit_value,
            {ATTR_UNIT_OF_MEASUREMENT: correct_unit},
        )
        await hass.async_block_till_done()

        set_or_remove_state(hass, entity_id, reset_state)
        await hass.async_block_till_done()
        set_or_remove_state(hass, entity_id, trigger_state)
        await hass.async_block_till_done()

        if i < len(limit_entities) - 1:
            # Not all limits fixed yet - should not fire
            assert len(calls) == 0
        else:
            # All limits fixed - should fire
            assert len(calls) == 1


async def assert_numerical_condition_unit_conversion(
    hass: HomeAssistant,
    *,
    condition: str,
    entity_id: str,
    pass_states: list[StateDescription],
    fail_states: list[StateDescription],
    numerical_condition_options: list[dict[str, Any]],
    limit_entity_condition_options: dict[str, Any],
    limit_entities: tuple[str, str],
    limit_entity_states: list[tuple[StateDescription, StateDescription]],
    invalid_limit_entity_states: list[tuple[StateDescription, StateDescription]],
) -> None:
    """Test unit conversion of a numerical condition.

    Verifies that a numerical condition correctly converts between units, both
    when limits are specified as numbers (with explicit units) and when limits
    come from entity references. Also verifies that the condition rejects limit
    entities whose unit_of_measurement is invalid (not convertible).

    Args:
        condition: The condition key (e.g. "climate.is_target_temperature").
        entity_id: The entity being evaluated by the condition.
        pass_states: Entity states that should make the condition pass.
        fail_states: Entity states that should make the condition fail.
        numerical_condition_options: List of condition option dicts, each
            specifying above/below thresholds with a unit. Every combination
            is tested against pass_states and fail_states.
        limit_entity_condition_options: Condition options dict using entity
            references for above/below (e.g. {CONF_ABOVE: "sensor.above"}).
        limit_entities: Tuple of (above_entity_id, below_entity_id) referenced
            by limit_entity_condition_options.
        limit_entity_states: List of (above_state, below_state) tuples, each
            providing valid states for the limit entities. Every combination
            is tested against pass_states and fail_states.
        invalid_limit_entity_states: Like limit_entity_states, but with invalid
            units. The condition should always fail regardless of entity state.

    """
    # Test limits set as number
    for condition_options in numerical_condition_options:
        cond = await create_target_condition(
            hass,
            condition=condition,
            target={CONF_ENTITY_ID: [entity_id]},
            behavior="any",
            condition_options=condition_options,
        )
        for state in pass_states:
            set_or_remove_state(hass, entity_id, state)
            assert cond.async_check() is True
        for state in fail_states:
            set_or_remove_state(hass, entity_id, state)
            assert cond.async_check() is False

    # Test limits set by entity
    cond = await create_target_condition(
        hass,
        condition=condition,
        target={CONF_ENTITY_ID: [entity_id]},
        behavior="any",
        condition_options=limit_entity_condition_options,
    )
    for limit_states in limit_entity_states:
        set_or_remove_state(hass, limit_entities[0], limit_states[0])
        set_or_remove_state(hass, limit_entities[1], limit_states[1])
        for state in pass_states:
            set_or_remove_state(hass, entity_id, state)
            assert cond.async_check() is True
        for state in fail_states:
            set_or_remove_state(hass, entity_id, state)
            assert cond.async_check() is False

    # Test invalid unit
    for limit_states in invalid_limit_entity_states:
        set_or_remove_state(hass, limit_entities[0], limit_states[0])
        set_or_remove_state(hass, limit_entities[1], limit_states[1])
        for state in pass_states:
            set_or_remove_state(hass, entity_id, state)
            assert cond.async_check() is False
        for state in fail_states:
            set_or_remove_state(hass, entity_id, state)
            assert cond.async_check() is False


async def assert_availability_follows_source_entity(
    hass: HomeAssistant,
    entity_id: str,
    source_entity_id: str,
) -> None:
    """Check that entity becomes unavailable when source entity is unavailable."""
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    hass.states.async_set(source_entity_id, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    hass.states.async_set(source_entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
