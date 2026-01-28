"""Test assist satellite conditions."""

from typing import Any

import pytest

from homeassistant.components.assist_satellite.entity import AssistSatelliteState
from homeassistant.core import HomeAssistant

from tests.components import (
    ConditionStateDescription,
    assert_condition_gated_by_labs_flag,
    create_target_condition,
    other_states,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture
async def target_assist_satellites(hass: HomeAssistant) -> list[str]:
    """Create multiple assist satellite entities associated with different targets."""
    return (await target_entities(hass, "assist_satellite"))["included"]


@pytest.mark.parametrize(
    "condition",
    [
        "assist_satellite.is_idle",
        "assist_satellite.is_listening",
        "assist_satellite.is_processing",
        "assist_satellite.is_responding",
    ],
)
async def test_assist_satellite_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the assist satellite conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("assist_satellite"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="assist_satellite.is_idle",
            target_states=[AssistSatelliteState.IDLE],
            other_states=other_states(AssistSatelliteState.IDLE),
        ),
        *parametrize_condition_states_any(
            condition="assist_satellite.is_listening",
            target_states=[AssistSatelliteState.LISTENING],
            other_states=other_states(AssistSatelliteState.LISTENING),
        ),
        *parametrize_condition_states_any(
            condition="assist_satellite.is_processing",
            target_states=[AssistSatelliteState.PROCESSING],
            other_states=other_states(AssistSatelliteState.PROCESSING),
        ),
        *parametrize_condition_states_any(
            condition="assist_satellite.is_responding",
            target_states=[AssistSatelliteState.RESPONDING],
            other_states=other_states(AssistSatelliteState.RESPONDING),
        ),
    ],
)
async def test_assist_satellite_state_condition_behavior_any(
    hass: HomeAssistant,
    target_assist_satellites: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the assist satellite state condition with the 'any' behavior."""
    other_entity_ids = set(target_assist_satellites) - {entity_id}

    # Set all assist satellites, including the tested one, to the initial state
    for eid in target_assist_satellites:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="any",
    )

    for state in states:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]

        # Check if changing other assist satellites also passes the condition
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("assist_satellite"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="assist_satellite.is_idle",
            target_states=[AssistSatelliteState.IDLE],
            other_states=other_states(AssistSatelliteState.IDLE),
        ),
        *parametrize_condition_states_all(
            condition="assist_satellite.is_listening",
            target_states=[AssistSatelliteState.LISTENING],
            other_states=other_states(AssistSatelliteState.LISTENING),
        ),
        *parametrize_condition_states_all(
            condition="assist_satellite.is_processing",
            target_states=[AssistSatelliteState.PROCESSING],
            other_states=other_states(AssistSatelliteState.PROCESSING),
        ),
        *parametrize_condition_states_all(
            condition="assist_satellite.is_responding",
            target_states=[AssistSatelliteState.RESPONDING],
            other_states=other_states(AssistSatelliteState.RESPONDING),
        ),
    ],
)
async def test_assist_satellite_state_condition_behavior_all(
    hass: HomeAssistant,
    target_assist_satellites: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the assist satellite state condition with the 'all' behavior."""
    other_entity_ids = set(target_assist_satellites) - {entity_id}

    # Set all assist satellites, including the tested one, to the initial state
    for eid in target_assist_satellites:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="all",
    )

    for state in states:
        included_state = state["included"]

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert condition(hass) == state["condition_true_first_entity"]

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()

        assert condition(hass) == state["condition_true"]
