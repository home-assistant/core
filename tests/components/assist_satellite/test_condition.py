"""Test assist satellite conditions."""

from typing import Any

import pytest

from homeassistant.components.assist_satellite.entity import AssistSatelliteState
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    other_states,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    target_entities,
)


@pytest.fixture
async def target_assist_satellites(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple assist satellite entities associated with different targets."""
    return await target_entities(hass, "assist_satellite")


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
    target_assist_satellites: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the assist satellite state condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_assist_satellites,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


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
    target_assist_satellites: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the assist satellite state condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_assist_satellites,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
