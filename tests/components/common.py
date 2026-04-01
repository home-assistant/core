"""Shared test helpers for components."""

from collections.abc import Iterable
import copy
from enum import StrEnum
import itertools
import logging
from typing import Any, TypedDict

import pytest

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
)
from homeassistant.helpers.trigger import async_initialize_triggers
from homeassistant.helpers.typing import UNDEFINED, TemplateVarsType, UndefinedType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_device_registry


async def target_entities(hass: HomeAssistant, domain: str) -> dict[str, list[str]]:
    """Create multiple entities associated with different targets.

    Returns a dict with the following keys:
    - included_entities: List of entity_ids meant to be targeted.
    - excluded_entities: List of entity_ids not meant to be targeted.
    """
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

    device = dr.DeviceEntry(id="test_device", area_id=area.id, labels={label.label_id})
    mock_device_registry(hass, {device.id: device})

    entity_reg = er.async_get(hass)
    # Entities associated with area
    entity_area = entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_area",
        suggested_object_id=f"area_{domain}",
    )
    entity_reg.async_update_entity(entity_area.entity_id, area_id=area.id)
    entity_area_excluded = entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_area_excluded",
        suggested_object_id=f"area_{domain}_excluded",
    )
    entity_reg.async_update_entity(entity_area_excluded.entity_id, area_id=area.id)

    # Entities associated with device
    entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_device",
        suggested_object_id=f"device_{domain}",
        device_id=device.id,
    )
    entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_device2",
        suggested_object_id=f"device2_{domain}",
        device_id=device.id,
    )
    entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_device_excluded",
        suggested_object_id=f"device_{domain}_excluded",
        device_id=device.id,
    )

    # Entities associated with label
    entity_label = entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_label",
        suggested_object_id=f"label_{domain}",
    )
    entity_reg.async_update_entity(entity_label.entity_id, labels={label.label_id})
    entity_label_excluded = entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_label_excluded",
        suggested_object_id=f"label_{domain}_excluded",
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
            f"{domain}.standalone_{domain}_excluded",
            f"{domain}.label_{domain}_excluded",
            f"{domain}.area_{domain}_excluded",
            f"{domain}.device_{domain}_excluded",
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
    """Test state and expected service call count for both included and excluded entities."""

    excluded_state: StateDescription  # State for entities not meant to be targeted


class ConditionStateDescription(TypedDict):
    """Test state and expected condition evaluation."""

    included_state: StateDescription  # State for entities meant to be targeted
    excluded_state: StateDescription  # State for entities not meant to be targeted

    condition_true: bool  # If the condition is expected to evaluate to true
    condition_true_first_entity: bool  # If the condition is expected to evaluate to true for the first targeted entity


def _parametrize_condition_states(
    *,
    condition: str,
    condition_options: dict[str, Any] | None = None,
    target_states: list[str | None | tuple[str | None, dict]],
    other_states: list[str | None | tuple[str | None, dict]],
    required_filter_attributes: dict | None,
    condition_true_if_invalid: bool,
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize states and expected condition evaluations.

    The target_states and other_states iterables are either iterables of
    states or iterables of (state, attributes) tuples.

    Returns a list of tuples with (condition, condition options, list of states),
    where states is a list of ConditionStateDescription dicts.
    """

    required_filter_attributes = required_filter_attributes or {}
    condition_options = condition_options or {}
    has_required_filter_attributes = bool(required_filter_attributes)

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
                    "state": state if has_required_filter_attributes else None,
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
                "state": state[0] if has_required_filter_attributes else None,
                "attributes": state[1],
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
    required_filter_attributes: dict | None = None,
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize states and expected condition evaluations.

    The target_states and other_states iterables are either iterables of
    states or iterables of (state, attributes) tuples.

    Returns a list of tuples with (condition, condition options, list of states),
    where states is a list of ConditionStateDescription dicts.
    """

    return _parametrize_condition_states(
        condition=condition,
        condition_options=condition_options,
        target_states=target_states,
        other_states=other_states,
        required_filter_attributes=required_filter_attributes,
        condition_true_if_invalid=False,
    )


def parametrize_condition_states_all(
    *,
    condition: str,
    condition_options: dict[str, Any] | None = None,
    target_states: list[str | None | tuple[str | None, dict]],
    other_states: list[str | None | tuple[str | None, dict]],
    required_filter_attributes: dict | None = None,
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize states and expected condition evaluations.

    The target_states and other_states iterables are either iterables of
    states or iterables of (state, attributes) tuples.

    Returns a list of tuples with (condition, condition options, list of states),
    where states is a list of ConditionStateDescription dicts.
    """

    return _parametrize_condition_states(
        condition=condition,
        condition_options=condition_options,
        target_states=target_states,
        other_states=other_states,
        required_filter_attributes=required_filter_attributes,
        condition_true_if_invalid=True,
    )


def parametrize_trigger_states(
    *,
    trigger: str,
    trigger_options: dict[str, Any] | None = None,
    target_states: list[str | None | tuple[str | None, dict]],
    other_states: list[str | None | tuple[str | None, dict]],
    extra_invalid_states: list[str | None | tuple[str | None, dict]] | None = None,
    required_filter_attributes: dict | None = None,
    trigger_from_none: bool = True,
    retrigger_on_target_state: bool = False,
) -> list[tuple[str, dict[str, Any], list[TriggerStateDescription]]]:
    """Parametrize states and expected service call counts.

    The target_states, other_states, and extra_invalid_states iterables are
    either iterables of states or iterables of (state, attributes) tuples.

    Set `trigger_from_none` to False if the trigger is not expected to fire
    when the initial state is None, this is relevant for triggers that limit
    entities to a certain device class because the device class can't be
    determined when the state is None.

    Set `retrigger_on_target_state` to True if the trigger is expected to fire
    when the state changes to another target state.

    Returns a list of tuples with (trigger, list of states),
    where states is a list of TriggerStateDescription dicts.
    """

    extra_invalid_states = extra_invalid_states or []
    invalid_states = [STATE_UNAVAILABLE, STATE_UNKNOWN, *extra_invalid_states]
    required_filter_attributes = required_filter_attributes or {}
    trigger_options = trigger_options or {}

    def state_with_attributes(
        state: str | None | tuple[str | None, dict], count: int
    ) -> TriggerStateDescription:
        """Return TriggerStateDescription dict."""
        if isinstance(state, str) or state is None:
            return {
                "included_state": {
                    "state": state,
                    "attributes": required_filter_attributes,
                },
                "excluded_state": {
                    "state": state if required_filter_attributes else None,
                    "attributes": {},
                },
                "count": count,
            }
        return {
            "included_state": {
                "state": state[0],
                "attributes": state[1] | required_filter_attributes,
            },
            "excluded_state": {
                "state": state[0] if required_filter_attributes else None,
                "attributes": state[1],
            },
            "count": count,
        }

    tests = [
        # Initial state None
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
        # Initial state different from target state
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
        # Initial state same as target state
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
        # Transition from other state to unavailable / unknown
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
        # Initial state unavailable / unknown + extra invalid states
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
        # If more than one target state, test state change between target states
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
) -> list[tuple[str, dict[str, Any], list[TriggerStateDescription]]]:
    """Parametrize states and expected service call counts for numerical changed triggers."""
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
                (state, {attribute: 0} | unit_attributes),
                (state, {attribute: 50} | unit_attributes),
                (state, {attribute: 100} | unit_attributes),
            ],
            other_states=[(state, {attribute: None} | unit_attributes)],
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
                (state, {attribute: 50} | unit_attributes),
                (state, {attribute: 100} | unit_attributes),
            ],
            other_states=[
                (state, {attribute: None} | unit_attributes),
                (state, {attribute: 0} | unit_attributes),
            ],
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
                (state, {attribute: 0} | unit_attributes),
                (state, {attribute: 50} | unit_attributes),
            ],
            other_states=[
                (state, {attribute: None} | unit_attributes),
                (state, {attribute: 100} | unit_attributes),
            ],
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
) -> list[tuple[str, dict[str, Any], list[TriggerStateDescription]]]:
    """Parametrize states and expected service call counts for numerical crossed threshold triggers."""
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
            target_states=[
                (state, {attribute: 50} | unit_attributes),
                (state, {attribute: 60} | unit_attributes),
            ],
            other_states=[
                (state, {attribute: None} | unit_attributes),
                (state, {attribute: 0} | unit_attributes),
                (state, {attribute: 100} | unit_attributes),
            ],
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
                (state, {attribute: 0} | unit_attributes),
                (state, {attribute: 100} | unit_attributes),
            ],
            other_states=[
                (state, {attribute: None} | unit_attributes),
                (state, {attribute: 50} | unit_attributes),
                (state, {attribute: 60} | unit_attributes),
            ],
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
                (state, {attribute: 50} | unit_attributes),
                (state, {attribute: 100} | unit_attributes),
            ],
            other_states=[
                (state, {attribute: None} | unit_attributes),
                (state, {attribute: 0} | unit_attributes),
            ],
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
                (state, {attribute: 0} | unit_attributes),
                (state, {attribute: 50} | unit_attributes),
            ],
            other_states=[
                (state, {attribute: None} | unit_attributes),
                (state, {attribute: 100} | unit_attributes),
            ],
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
    """Parametrize states and expected service call counts for numerical state-value changed triggers.

    Unlike parametrize_numerical_attribute_changed_trigger_states, this is for
    entities where the tracked numerical value is in state.state (e.g. sensor
    entities), not in an attribute.
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
    """Parametrize states and expected service call counts for numerical state-value crossed threshold triggers.

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
            target_states=[("50", unit_attributes), ("60", unit_attributes)],
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
                ("50", unit_attributes),
                ("60", unit_attributes),
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
    """Arm the specified trigger and record fired entity_ids in calls when it triggers."""
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

    await async_initialize_triggers(
        hass,
        [trigger_config],
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
    return await async_condition_from_config(
        hass,
        {
            CONF_CONDITION: condition,
            CONF_TARGET: target,
            CONF_OPTIONS: {"behavior": behavior, **(condition_options or {})},
        },
    )


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


async def assert_condition_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Helper to check that a condition is gated by the labs flag."""

    # Local include to avoid importing the automation component unnecessarily
    from homeassistant.components import automation  # noqa: PLC0415

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    CONF_CONDITION: condition,
                    CONF_TARGET: {ATTR_LABEL_ID: "test_label"},
                    CONF_OPTIONS: {"behavior": "any"},
                },
                "action": {
                    "service": "test.automation",
                },
            }
        },
    )

    assert (
        "Unnamed automation failed to setup conditions and has been disabled: "
        f"Condition '{condition}' requires the experimental 'New triggers and "
        "conditions' feature to be enabled in Home Assistant Labs settings "
        "(feature flag: 'new_triggers_conditions')"
    ) in caplog.text


async def assert_trigger_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger: str
) -> None:
    """Helper to check that a trigger is gated by the labs flag."""

    # Local include to avoid importing the automation component unnecessarily
    from homeassistant.components import automation  # noqa: PLC0415

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: trigger,
                    CONF_TARGET: {ATTR_LABEL_ID: "test_label"},
                },
                "action": {
                    "service": "test.automation",
                },
            }
        },
    )

    assert (
        "Unnamed automation failed to setup triggers and has been disabled: Trigger "
        f"'{trigger}' requires the experimental 'New triggers and conditions' "
        "feature to be enabled in Home Assistant Labs settings (feature flag: "
        "'new_triggers_conditions')"
    ) in caplog.text


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
        assert cond(hass) is False

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert cond(hass) == state["condition_true"]

        # Set other included entities to the included state to verify that
        # they don't change the condition evaluation
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert cond(hass) == state["condition_true"]


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
        assert cond(hass) == state["condition_true_first_entity"]

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        for excluded_entity_id in excluded_entity_ids:
            set_or_remove_state(hass, excluded_entity_id, excluded_state)
            await hass.async_block_till_done()

        assert cond(hass) == state["condition_true"]


async def assert_trigger_behavior_any(
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
    """Test trigger fires in mode any."""
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
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(calls) == state["count"]
        for call in calls:
            assert call == entity_id
        calls.clear()

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        for excluded_entity_id in excluded_entity_ids:
            set_or_remove_state(hass, excluded_entity_id, excluded_state)
            await hass.async_block_till_done()
        assert len(calls) == (entities_in_target - 1) * state["count"]
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
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(calls) == state["count"]
        for call in calls:
            assert call == entity_id
        calls.clear()

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        for excluded_entity_id in excluded_entity_ids:
            set_or_remove_state(hass, excluded_entity_id, excluded_state)
            await hass.async_block_till_done()
        assert len(calls) == 0


async def assert_trigger_behavior_last(
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
    """Test trigger fires in mode last."""
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
        {"behavior": "last"} | trigger_options,
        trigger_target_config,
        calls,
    )

    for state in states[1:]:
        excluded_state = state["excluded_state"]
        included_state = state["included_state"]
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
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
    """Parametrize above/below threshold test cases for numerical conditions.

    Returns a list of tuples with (condition, condition_options, states).
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
                ("21", unit_attributes),
                ("50", unit_attributes),
                ("79", unit_attributes),
            ],
            other_states=[
                ("0", unit_attributes),
                ("20", unit_attributes),
                ("80", unit_attributes),
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
    """Parametrize above/below threshold test cases for numerical conditions with 'all' behavior.

    Returns a list of tuples with (condition, condition_options, states).
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
                ("21", unit_attributes),
                ("50", unit_attributes),
                ("79", unit_attributes),
            ],
            other_states=[
                ("0", unit_attributes),
                ("20", unit_attributes),
                ("80", unit_attributes),
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
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize above/below threshold test cases for attribute-based numerical conditions.

    Returns a list of tuples with (condition, condition_options, states).
    """
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
                (state, {attribute: 21} | unit_attributes),
                (state, {attribute: 50} | unit_attributes),
                (state, {attribute: 100} | unit_attributes),
            ],
            other_states=[
                (state, {attribute: 0} | unit_attributes),
                (state, {attribute: 10} | unit_attributes),
                (state, {attribute: 20} | unit_attributes),
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
                (state, {attribute: 0} | unit_attributes),
                (state, {attribute: 50} | unit_attributes),
                (state, {attribute: 79} | unit_attributes),
            ],
            other_states=[
                (state, {attribute: 80} | unit_attributes),
                (state, {attribute: 90} | unit_attributes),
                (state, {attribute: 100} | unit_attributes),
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
                (state, {attribute: 21} | unit_attributes),
                (state, {attribute: 50} | unit_attributes),
                (state, {attribute: 79} | unit_attributes),
            ],
            other_states=[
                (state, {attribute: 0} | unit_attributes),
                (state, {attribute: 20} | unit_attributes),
                (state, {attribute: 80} | unit_attributes),
                (state, {attribute: 100} | unit_attributes),
            ],
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
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize above/below threshold test cases for attribute-based numerical conditions with 'all' behavior.

    Returns a list of tuples with (condition, condition_options, states).
    """
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
                (state, {attribute: 21} | unit_attributes),
                (state, {attribute: 50} | unit_attributes),
                (state, {attribute: 100} | unit_attributes),
            ],
            other_states=[
                (state, {attribute: 0} | unit_attributes),
                (state, {attribute: 10} | unit_attributes),
                (state, {attribute: 20} | unit_attributes),
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
                (state, {attribute: 0} | unit_attributes),
                (state, {attribute: 50} | unit_attributes),
                (state, {attribute: 79} | unit_attributes),
            ],
            other_states=[
                (state, {attribute: 80} | unit_attributes),
                (state, {attribute: 90} | unit_attributes),
                (state, {attribute: 100} | unit_attributes),
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
                (state, {attribute: 21} | unit_attributes),
                (state, {attribute: 50} | unit_attributes),
                (state, {attribute: 79} | unit_attributes),
            ],
            other_states=[
                (state, {attribute: 0} | unit_attributes),
                (state, {attribute: 20} | unit_attributes),
                (state, {attribute: 80} | unit_attributes),
                (state, {attribute: 100} | unit_attributes),
            ],
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
        condition: The condition key (e.g. "climate.target_temperature").
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
            assert cond(hass) is True
        for state in fail_states:
            set_or_remove_state(hass, entity_id, state)
            assert cond(hass) is False

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
            assert cond(hass) is True
        for state in fail_states:
            set_or_remove_state(hass, entity_id, state)
            assert cond(hass) is False

    # Test invalid unit
    for limit_states in invalid_limit_entity_states:
        set_or_remove_state(hass, limit_entities[0], limit_states[0])
        set_or_remove_state(hass, limit_entities[1], limit_states[1])
        for state in pass_states:
            set_or_remove_state(hass, entity_id, state)
            assert cond(hass) is False
        for state in fail_states:
            set_or_remove_state(hass, entity_id, state)
            assert cond(hass) is False
