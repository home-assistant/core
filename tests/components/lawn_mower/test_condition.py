"""Test lawn mower conditions."""

from typing import Any

import pytest

from homeassistant.components.lawn_mower.const import LawnMowerActivity
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
async def target_lawn_mowers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple lawn mower entities associated with different targets."""
    return await target_entities(hass, "lawn_mower")


@pytest.mark.parametrize(
    "condition",
    [
        "lawn_mower.is_docked",
        "lawn_mower.is_encountering_an_error",
        "lawn_mower.is_mowing",
        "lawn_mower.is_paused",
        "lawn_mower.is_returning",
    ],
)
async def test_lawn_mower_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the lawn mower conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("lawn_mower"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="lawn_mower.is_docked",
            target_states=[LawnMowerActivity.DOCKED],
            other_states=other_states(LawnMowerActivity.DOCKED),
        ),
        *parametrize_condition_states_any(
            condition="lawn_mower.is_encountering_an_error",
            target_states=[LawnMowerActivity.ERROR],
            other_states=other_states(LawnMowerActivity.ERROR),
        ),
        *parametrize_condition_states_any(
            condition="lawn_mower.is_mowing",
            target_states=[LawnMowerActivity.MOWING],
            other_states=other_states(LawnMowerActivity.MOWING),
        ),
        *parametrize_condition_states_any(
            condition="lawn_mower.is_paused",
            target_states=[LawnMowerActivity.PAUSED],
            other_states=other_states(LawnMowerActivity.PAUSED),
        ),
        *parametrize_condition_states_any(
            condition="lawn_mower.is_returning",
            target_states=[LawnMowerActivity.RETURNING],
            other_states=other_states(LawnMowerActivity.RETURNING),
        ),
    ],
)
async def test_lawn_mower_state_condition_behavior_any(
    hass: HomeAssistant,
    target_lawn_mowers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the lawn mower state condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_lawn_mowers,
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
    parametrize_target_entities("lawn_mower"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="lawn_mower.is_docked",
            target_states=[LawnMowerActivity.DOCKED],
            other_states=other_states(LawnMowerActivity.DOCKED),
        ),
        *parametrize_condition_states_all(
            condition="lawn_mower.is_encountering_an_error",
            target_states=[LawnMowerActivity.ERROR],
            other_states=other_states(LawnMowerActivity.ERROR),
        ),
        *parametrize_condition_states_all(
            condition="lawn_mower.is_mowing",
            target_states=[LawnMowerActivity.MOWING],
            other_states=other_states(LawnMowerActivity.MOWING),
        ),
        *parametrize_condition_states_all(
            condition="lawn_mower.is_paused",
            target_states=[LawnMowerActivity.PAUSED],
            other_states=other_states(LawnMowerActivity.PAUSED),
        ),
        *parametrize_condition_states_all(
            condition="lawn_mower.is_returning",
            target_states=[LawnMowerActivity.RETURNING],
            other_states=other_states(LawnMowerActivity.RETURNING),
        ),
    ],
)
async def test_lawn_mower_state_condition_behavior_all(
    hass: HomeAssistant,
    target_lawn_mowers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the lawn mower state condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_lawn_mowers,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
