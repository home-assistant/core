"""Test gate trigger."""

from typing import Any

import pytest

from homeassistant.components.cover import ATTR_IS_CLOSED, CoverState
from homeassistant.const import ATTR_DEVICE_CLASS, CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall

from tests.components.common import (
    TriggerStateDescription,
    arm_trigger,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_gated_by_labs_flag,
    parametrize_target_entities,
    parametrize_trigger_states,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture
async def target_covers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple cover entities associated with different targets."""
    return await target_entities(hass, "cover")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "gate.opened",
        "gate.closed",
    ],
)
async def test_gate_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the gate triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="gate.opened",
            target_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
            ],
            other_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            extra_invalid_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: None}),
                (CoverState.OPEN, {}),
            ],
            additional_attributes={ATTR_DEVICE_CLASS: "gate"},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="gate.closed",
            target_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            other_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
            ],
            extra_invalid_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: None}),
                (CoverState.OPEN, {}),
            ],
            additional_attributes={ATTR_DEVICE_CLASS: "gate"},
            trigger_from_none=False,
        ),
    ],
)
async def test_gate_trigger_cover_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_covers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test gate trigger fires for cover entities with device_class gate."""
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
        target_entities=target_covers,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="gate.opened",
            target_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
            ],
            other_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            extra_invalid_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: None}),
                (CoverState.OPEN, {}),
            ],
            additional_attributes={ATTR_DEVICE_CLASS: "gate"},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="gate.closed",
            target_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            other_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
            ],
            extra_invalid_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: None}),
                (CoverState.OPEN, {}),
            ],
            additional_attributes={ATTR_DEVICE_CLASS: "gate"},
            trigger_from_none=False,
        ),
    ],
)
async def test_gate_trigger_cover_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_covers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test gate trigger fires on the first cover state change."""
    await assert_trigger_behavior_first(
        hass,
        service_calls=service_calls,
        target_entities=target_covers,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="gate.opened",
            target_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
            ],
            other_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            extra_invalid_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: None}),
                (CoverState.OPEN, {}),
            ],
            additional_attributes={ATTR_DEVICE_CLASS: "gate"},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="gate.closed",
            target_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            other_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
            ],
            extra_invalid_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: None}),
                (CoverState.OPEN, {}),
            ],
            additional_attributes={ATTR_DEVICE_CLASS: "gate"},
            trigger_from_none=False,
        ),
    ],
)
async def test_gate_trigger_cover_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_covers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test gate trigger fires when the last cover changes state."""
    other_entity_ids = set(target_covers["included"]) - {entity_id}
    excluded_entity_ids = set(target_covers["excluded"]) - {entity_id}

    for eid in target_covers["included"]:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()
    for eid in excluded_entity_ids:
        set_or_remove_state(hass, eid, states[0]["excluded"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "last"}, trigger_target_config)

    for state in states[1:]:
        excluded_state = state["excluded"]
        included_state = state["included"]
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, excluded_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        for excluded_entity_id in excluded_entity_ids:
            set_or_remove_state(hass, excluded_entity_id, excluded_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    (
        "trigger_key",
        "cover_initial",
        "cover_initial_is_closed",
        "cover_target",
        "cover_target_is_closed",
    ),
    [
        (
            "gate.opened",
            CoverState.CLOSED,
            True,
            CoverState.OPEN,
            False,
        ),
        (
            "gate.closed",
            CoverState.OPEN,
            False,
            CoverState.CLOSED,
            True,
        ),
    ],
)
async def test_gate_trigger_excludes_non_gate_device_class(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    trigger_key: str,
    cover_initial: str,
    cover_initial_is_closed: bool,
    cover_target: str,
    cover_target_is_closed: bool,
) -> None:
    """Test gate trigger does not fire for entities without device_class gate."""
    entity_id_cover_gate = "cover.test_gate"
    entity_id_cover_garage = "cover.test_garage"

    # Set initial states
    hass.states.async_set(
        entity_id_cover_gate,
        cover_initial,
        {ATTR_DEVICE_CLASS: "gate", ATTR_IS_CLOSED: cover_initial_is_closed},
    )
    hass.states.async_set(
        entity_id_cover_garage,
        cover_initial,
        {ATTR_DEVICE_CLASS: "garage", ATTR_IS_CLOSED: cover_initial_is_closed},
    )
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        trigger_key,
        {},
        {
            CONF_ENTITY_ID: [
                entity_id_cover_gate,
                entity_id_cover_garage,
            ]
        },
    )

    # Gate cover changes - should trigger
    hass.states.async_set(
        entity_id_cover_gate,
        cover_target,
        {ATTR_DEVICE_CLASS: "gate", ATTR_IS_CLOSED: cover_target_is_closed},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id_cover_gate
    service_calls.clear()

    # Garage cover changes - should NOT trigger (wrong device class)
    hass.states.async_set(
        entity_id_cover_garage,
        cover_target,
        {ATTR_DEVICE_CLASS: "garage", ATTR_IS_CLOSED: cover_target_is_closed},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0
