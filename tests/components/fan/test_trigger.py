"""Test fan trigger."""

import pytest

from homeassistant.const import CONF_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.components import (
    arm_trigger,
    parametrize_target_entities,
    parametrize_trigger_states,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
async def target_fans(hass: HomeAssistant) -> None:
    """Create multiple fan entities associated with different targets."""
    return await target_entities(hass, "fan")


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("fan"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states("fan.turned_on", (STATE_ON,), (STATE_OFF,)),
        *parametrize_trigger_states("fan.turned_off", (STATE_OFF,), (STATE_ON,)),
    ],
)
async def test_fan_state_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_fans: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[tuple[str, int]],
) -> None:
    """Test that the fan state trigger fires when any fan state changes to a specific state."""
    await async_setup_component(hass, "fan", {})

    other_entity_ids = set(target_fans) - {entity_id}

    # Set all fans, including the tested fan, to the initial state
    for eid in target_fans:
        set_or_remove_state(hass, eid, states[0][0])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {}, trigger_target_config)

    for state, expected_calls in states[1:]:
        set_or_remove_state(hass, entity_id, state)
        await hass.async_block_till_done()
        assert len(service_calls) == expected_calls
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other fans also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * expected_calls
        service_calls.clear()


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("fan"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states("fan.turned_on", (STATE_ON,), (STATE_OFF,)),
        *parametrize_trigger_states("fan.turned_off", (STATE_OFF,), (STATE_ON,)),
    ],
)
async def test_fan_state_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_fans: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[tuple[str, int, list[str]]],
) -> None:
    """Test that the fan state trigger fires when the first fan changes to a specific state."""
    await async_setup_component(hass, "fan", {})

    other_entity_ids = set(target_fans) - {entity_id}

    # Set all fans, including the tested fan, to the initial state
    for eid in target_fans:
        set_or_remove_state(hass, eid, states[0][0])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "first"}, trigger_target_config)

    for state, expected_calls in states[1:]:
        set_or_remove_state(hass, entity_id, state)
        await hass.async_block_till_done()
        assert len(service_calls) == expected_calls
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other fans should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("fan"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states("fan.turned_on", (STATE_ON,), (STATE_OFF,)),
        *parametrize_trigger_states("fan.turned_off", (STATE_OFF,), (STATE_ON,)),
    ],
)
async def test_fan_state_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_fans: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[tuple[str, int]],
) -> None:
    """Test that the fan state trigger fires when the last fan changes to a specific state."""
    await async_setup_component(hass, "fan", {})

    other_entity_ids = set(target_fans) - {entity_id}

    # Set all fans, including the tested fan, to the initial state
    for eid in target_fans:
        set_or_remove_state(hass, eid, states[0][0])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "last"}, trigger_target_config)

    for state, expected_calls in states[1:]:
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(hass, entity_id, state)
        await hass.async_block_till_done()
        assert len(service_calls) == expected_calls
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()
