"""Test assist satellite triggers."""

import pytest

from homeassistant.components.assist_satellite.entity import AssistSatelliteState
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.components import (
    arm_trigger,
    parametrize_target_entities,
    parametrize_trigger_states,
    set_or_remove_state,
    target_entities,
)

ASSIST_SATELLITE_STATES = {s.value for s in AssistSatelliteState}


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
async def target_assist_satellites(hass: HomeAssistant) -> None:
    """Create multiple assist satellite entities associated with different targets."""
    return await target_entities(hass, "assist_satellite")


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("assist_satellite"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states(
            "assist_satellite.idle",
            (AssistSatelliteState.IDLE,),
            ASSIST_SATELLITE_STATES - {AssistSatelliteState.IDLE},
        ),
        *parametrize_trigger_states(
            "assist_satellite.listening",
            (AssistSatelliteState.LISTENING,),
            ASSIST_SATELLITE_STATES - {AssistSatelliteState.LISTENING},
        ),
        *parametrize_trigger_states(
            "assist_satellite.processing",
            (AssistSatelliteState.PROCESSING,),
            ASSIST_SATELLITE_STATES - {AssistSatelliteState.PROCESSING},
        ),
        *parametrize_trigger_states(
            "assist_satellite.responding",
            (AssistSatelliteState.RESPONDING,),
            ASSIST_SATELLITE_STATES - {AssistSatelliteState.RESPONDING},
        ),
    ],
)
async def test_assist_satellite_state_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_assist_satellites: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[tuple[str, int]],
) -> None:
    """Test that the assist satellite state trigger fires when any assist satellite state changes to a specific state."""
    await async_setup_component(hass, "assist_satellite", {})

    other_entity_ids = set(target_assist_satellites) - {entity_id}

    # Set all assist satellites, including the tested one, to the initial state
    for eid in target_assist_satellites:
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

        # Check if changing other assist satellites also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * expected_calls
        service_calls.clear()


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("assist_satellite"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states(
            "assist_satellite.idle",
            (AssistSatelliteState.IDLE,),
            ASSIST_SATELLITE_STATES - {AssistSatelliteState.IDLE},
        ),
        *parametrize_trigger_states(
            "assist_satellite.listening",
            (AssistSatelliteState.LISTENING,),
            ASSIST_SATELLITE_STATES - {AssistSatelliteState.LISTENING},
        ),
        *parametrize_trigger_states(
            "assist_satellite.processing",
            (AssistSatelliteState.PROCESSING,),
            ASSIST_SATELLITE_STATES - {AssistSatelliteState.PROCESSING},
        ),
        *parametrize_trigger_states(
            "assist_satellite.responding",
            (AssistSatelliteState.RESPONDING,),
            ASSIST_SATELLITE_STATES - {AssistSatelliteState.RESPONDING},
        ),
    ],
)
async def test_assist_satellite_state_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_assist_satellites: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[tuple[str, int, list[str]]],
) -> None:
    """Test that the assist satellite state trigger fires when the first assist satellite changes to a specific state."""
    await async_setup_component(hass, "assist_satellite", {})

    other_entity_ids = set(target_assist_satellites) - {entity_id}

    # Set all assist satellites, including the tested one, to the initial state
    for eid in target_assist_satellites:
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

        # Triggering other assist satellites should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("assist_satellite"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states(
            "assist_satellite.idle",
            (AssistSatelliteState.IDLE,),
            ASSIST_SATELLITE_STATES - {AssistSatelliteState.IDLE},
        ),
        *parametrize_trigger_states(
            "assist_satellite.listening",
            (AssistSatelliteState.LISTENING,),
            ASSIST_SATELLITE_STATES - {AssistSatelliteState.LISTENING},
        ),
        *parametrize_trigger_states(
            "assist_satellite.processing",
            (AssistSatelliteState.PROCESSING,),
            ASSIST_SATELLITE_STATES - {AssistSatelliteState.PROCESSING},
        ),
        *parametrize_trigger_states(
            "assist_satellite.responding",
            (AssistSatelliteState.RESPONDING,),
            ASSIST_SATELLITE_STATES - {AssistSatelliteState.RESPONDING},
        ),
    ],
)
async def test_assist_satellite_state_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_assist_satellites: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[tuple[str, int]],
) -> None:
    """Test that the assist_satellite state trigger fires when the last assist_satellite changes to a specific state."""
    await async_setup_component(hass, "assist_satellite", {})

    other_entity_ids = set(target_assist_satellites) - {entity_id}

    # Set all assist satellites, including the tested one, to the initial state
    for eid in target_assist_satellites:
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
