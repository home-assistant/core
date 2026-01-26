"""The tests for components."""

from collections.abc import Iterable
from enum import StrEnum
import itertools
from typing import Any, TypedDict

import pytest

from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    CONF_ABOVE,
    CONF_BELOW,
    CONF_CONDITION,
    CONF_ENTITY_ID,
    CONF_OPTIONS,
    CONF_PLATFORM,
    CONF_TARGET,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
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
from homeassistant.helpers.trigger import (
    CONF_LOWER_LIMIT,
    CONF_THRESHOLD_TYPE,
    CONF_UPPER_LIMIT,
    ThresholdType,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_device_registry


async def target_entities(
    hass: HomeAssistant, domain: str
) -> tuple[list[str], list[str]]:
    """Create multiple entities associated with different targets.

    Returns a dict with the following keys:
    - included: List of entity_ids meant to be targeted.
    - excluded: List of entity_ids not meant to be targeted.
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
        "included": [
            f"{domain}.standalone_{domain}",
            f"{domain}.standalone2_{domain}",
            f"{domain}.label_{domain}",
            f"{domain}.area_{domain}",
            f"{domain}.device_{domain}",
            f"{domain}.device2_{domain}",
        ],
        "excluded": [
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


class _StateDescription(TypedDict):
    """Test state with attributes."""

    state: str | None
    attributes: dict


class TriggerStateDescription(TypedDict):
    """Test state and expected service call count."""

    included: _StateDescription  # State for entities meant to be targeted
    excluded: _StateDescription  # State for entities not meant to be targeted
    count: int  # Expected service call count


class ConditionStateDescription(TypedDict):
    """Test state and expected condition evaluation."""

    included: _StateDescription  # State for entities meant to be targeted
    excluded: _StateDescription  # State for entities not meant to be targeted

    condition_true: bool  # If the condition is expected to evaluate to true
    condition_true_first_entity: bool  # If the condition is expected to evaluate to true for the first targeted entity


def _parametrize_condition_states(
    *,
    condition: str,
    condition_options: dict[str, Any] | None = None,
    target_states: list[str | None | tuple[str | None, dict]],
    other_states: list[str | None | tuple[str | None, dict]],
    additional_attributes: dict | None,
    condition_true_if_invalid: bool,
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize states and expected condition evaluations.

    The target_states and other_states iterables are either iterables of
    states or iterables of (state, attributes) tuples.

    Returns a list of tuples with (condition, condition options, list of states),
    where states is a list of ConditionStateDescription dicts.
    """

    additional_attributes = additional_attributes or {}
    condition_options = condition_options or {}

    def state_with_attributes(
        state: str | None | tuple[str | None, dict],
        condition_true: bool,
        condition_true_first_entity: bool,
    ) -> ConditionStateDescription:
        """Return ConditionStateDescription dict."""
        if isinstance(state, str) or state is None:
            return {
                "included": {
                    "state": state,
                    "attributes": additional_attributes,
                },
                "excluded": {
                    "state": state,
                    "attributes": {},
                },
                "condition_true": condition_true,
                "condition_true_first_entity": condition_true_first_entity,
            }
        return {
            "included": {
                "state": state[0],
                "attributes": state[1] | additional_attributes,
            },
            "excluded": {
                "state": state[0],
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
    additional_attributes: dict | None = None,
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
        additional_attributes=additional_attributes,
        condition_true_if_invalid=False,
    )


def parametrize_condition_states_all(
    *,
    condition: str,
    condition_options: dict[str, Any] | None = None,
    target_states: list[str | None | tuple[str | None, dict]],
    other_states: list[str | None | tuple[str | None, dict]],
    additional_attributes: dict | None = None,
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
        additional_attributes=additional_attributes,
        condition_true_if_invalid=True,
    )


def parametrize_trigger_states(
    *,
    trigger: str,
    trigger_options: dict[str, Any] | None = None,
    target_states: list[str | None | tuple[str | None, dict]],
    other_states: list[str | None | tuple[str | None, dict]],
    additional_attributes: dict | None = None,
    trigger_from_none: bool = True,
    retrigger_on_target_state: bool = False,
) -> list[tuple[str, dict[str, Any], list[TriggerStateDescription]]]:
    """Parametrize states and expected service call counts.

    The target_states and other_states iterables are either iterables of
    states or iterables of (state, attributes) tuples.

    Set `trigger_from_none` to False if the trigger is not expected to fire
    when the initial state is None.

    Set `retrigger_on_target_state` to True if the trigger is expected to fire
    when the state changes to another target state.

    Returns a list of tuples with (trigger, list of states),
    where states is a list of TriggerStateDescription dicts.
    """

    additional_attributes = additional_attributes or {}
    trigger_options = trigger_options or {}

    def state_with_attributes(
        state: str | None | tuple[str | None, dict], count: int
    ) -> TriggerStateDescription:
        """Return TriggerStateDescription dict."""
        if isinstance(state, str) or state is None:
            return {
                "included": {
                    "state": state,
                    "attributes": additional_attributes,
                },
                "excluded": {
                    "state": state,
                    "attributes": {},
                },
                "count": count,
            }
        return {
            "included": {
                "state": state[0],
                "attributes": state[1] | additional_attributes,
            },
            "excluded": {
                "state": state[0],
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
            # other_state,
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
        # Initial state unavailable / unknown
        (
            trigger,
            trigger_options,
            list(
                itertools.chain.from_iterable(
                    (
                        state_with_attributes(STATE_UNAVAILABLE, 0),
                        state_with_attributes(target_state, 0),
                        state_with_attributes(other_state, 0),
                        state_with_attributes(target_state, 1),
                    )
                    for target_state in target_states
                    for other_state in other_states
                )
            ),
        ),
        (
            trigger,
            trigger_options,
            list(
                itertools.chain.from_iterable(
                    (
                        state_with_attributes(STATE_UNKNOWN, 0),
                        state_with_attributes(target_state, 0),
                        state_with_attributes(other_state, 0),
                        state_with_attributes(target_state, 1),
                    )
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


def parametrize_numerical_attribute_changed_trigger_states(
    trigger: str, state: str, attribute: str
) -> list[tuple[str, dict[str, Any], list[TriggerStateDescription]]]:
    """Parametrize states and expected service call counts for numerical changed triggers."""
    return [
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options={},
            target_states=[
                (state, {attribute: 0}),
                (state, {attribute: 50}),
                (state, {attribute: 100}),
            ],
            other_states=[(state, {attribute: None})],
            retrigger_on_target_state=True,
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options={CONF_ABOVE: 10},
            target_states=[
                (state, {attribute: 50}),
                (state, {attribute: 100}),
            ],
            other_states=[
                (state, {attribute: None}),
                (state, {attribute: 0}),
            ],
            retrigger_on_target_state=True,
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options={CONF_BELOW: 90},
            target_states=[
                (state, {attribute: 0}),
                (state, {attribute: 50}),
            ],
            other_states=[
                (state, {attribute: None}),
                (state, {attribute: 100}),
            ],
            retrigger_on_target_state=True,
        ),
    ]


def parametrize_numerical_attribute_crossed_threshold_trigger_states(
    trigger: str, state: str, attribute: str
) -> list[tuple[str, dict[str, Any], list[TriggerStateDescription]]]:
    """Parametrize states and expected service call counts for numerical crossed threshold triggers."""
    return [
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options={
                CONF_THRESHOLD_TYPE: ThresholdType.BETWEEN,
                CONF_LOWER_LIMIT: 10,
                CONF_UPPER_LIMIT: 90,
            },
            target_states=[
                (state, {attribute: 50}),
                (state, {attribute: 60}),
            ],
            other_states=[
                (state, {attribute: None}),
                (state, {attribute: 0}),
                (state, {attribute: 100}),
            ],
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options={
                CONF_THRESHOLD_TYPE: ThresholdType.OUTSIDE,
                CONF_LOWER_LIMIT: 10,
                CONF_UPPER_LIMIT: 90,
            },
            target_states=[
                (state, {attribute: 0}),
                (state, {attribute: 100}),
            ],
            other_states=[
                (state, {attribute: None}),
                (state, {attribute: 50}),
                (state, {attribute: 60}),
            ],
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options={
                CONF_THRESHOLD_TYPE: ThresholdType.ABOVE,
                CONF_LOWER_LIMIT: 10,
            },
            target_states=[
                (state, {attribute: 50}),
                (state, {attribute: 100}),
            ],
            other_states=[
                (state, {attribute: None}),
                (state, {attribute: 0}),
            ],
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options={
                CONF_THRESHOLD_TYPE: ThresholdType.BELOW,
                CONF_UPPER_LIMIT: 90,
            },
            target_states=[
                (state, {attribute: 0}),
                (state, {attribute: 50}),
            ],
            other_states=[
                (state, {attribute: None}),
                (state, {attribute: 100}),
            ],
        ),
    ]


async def arm_trigger(
    hass: HomeAssistant,
    trigger: str,
    trigger_options: dict[str, Any] | None,
    trigger_target: dict,
) -> None:
    """Arm the specified trigger, call service test.automation when it triggers."""

    # Local include to avoid importing the automation component unnecessarily
    from homeassistant.components import automation  # noqa: PLC0415

    options = {CONF_OPTIONS: {**trigger_options}} if trigger_options is not None else {}

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: trigger,
                    CONF_TARGET: {**trigger_target},
                }
                | options,
                "action": {
                    "service": "test.automation",
                    "data_template": {CONF_ENTITY_ID: "{{ trigger.entity_id }}"},
                },
            }
        },
    )


async def create_target_condition(
    hass: HomeAssistant,
    *,
    condition: str,
    target: dict,
    behavior: str,
) -> ConditionCheckerTypeOptional:
    """Create a target condition."""
    return await async_condition_from_config(
        hass,
        {
            CONF_CONDITION: condition,
            CONF_TARGET: target,
            CONF_OPTIONS: {"behavior": behavior},
        },
    )


def set_or_remove_state(
    hass: HomeAssistant,
    entity_id: str,
    state: TriggerStateDescription,
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
