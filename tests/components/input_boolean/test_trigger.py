"""Test input boolean triggers."""

from typing import Any

import pytest

from homeassistant.components.input_boolean import DOMAIN
from homeassistant.const import CONF_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, ServiceCall

from tests.components import (
    TriggerStateDescription,
    arm_trigger,
    assert_trigger_gated_by_labs_flag,
    parametrize_target_entities,
    parametrize_trigger_states,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture
async def target_input_booleans(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple input_boolean entities associated with different targets."""
    return await target_entities(hass, DOMAIN)


@pytest.mark.parametrize(
    "trigger_key",
    [
        "input_boolean.turned_off",
        "input_boolean.turned_on",
    ],
)
async def test_input_boolean_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the input_boolean triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="input_boolean.turned_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
        *parametrize_trigger_states(
            trigger="input_boolean.turned_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
    ],
)
async def test_input_boolean_state_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_input_booleans: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the input_boolean state trigger fires when any input_boolean state changes to a specific state."""
    other_entity_ids = set(target_input_booleans["included"]) - {entity_id}

    # Set all input_booleans, including the tested one, to the initial state
    for eid in target_input_booleans["included"]:
        set_or_remove_state(hass, eid, states[0]["included"])
    await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {}, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other input_booleans also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="input_boolean.turned_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
        *parametrize_trigger_states(
            trigger="input_boolean.turned_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
    ],
)
async def test_input_boolean_state_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_input_booleans: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the input_boolean state trigger fires when the first input_boolean changes to a specific state."""
    other_entity_ids = set(target_input_booleans["included"]) - {entity_id}

    # Set all input_booleans, including the tested one, to the initial state
    for eid in target_input_booleans["included"]:
        set_or_remove_state(hass, eid, states[0]["included"])
    await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "first"}, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other input_booleans should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="input_boolean.turned_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
        *parametrize_trigger_states(
            trigger="input_boolean.turned_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
    ],
)
async def test_input_boolean_state_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_input_booleans: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the input_boolean state trigger fires when the last input_boolean changes to a specific state."""
    other_entity_ids = set(target_input_booleans["included"]) - {entity_id}

    # Set all input_booleans, including the tested one, to the initial state
    for eid in target_input_booleans["included"]:
        set_or_remove_state(hass, eid, states[0]["included"])
    await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "last"}, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()
