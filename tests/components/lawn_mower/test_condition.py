"""Test lawn mower conditions."""

from typing import Any

import pytest

from homeassistant.components.lawn_mower.const import LawnMowerActivity
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
async def target_lawn_mowers(hass: HomeAssistant) -> list[str]:
    """Create multiple lawn mower entities associated with different targets."""
    return (await target_entities(hass, "lawn_mower"))["included"]


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
    target_lawn_mowers: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the lawn mower state condition with the 'any' behavior."""
    other_entity_ids = set(target_lawn_mowers) - {entity_id}

    # Set all lawn mowers, including the tested lawn mower, to the initial state
    for eid in target_lawn_mowers:
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

        # Check if changing other lawn mowers also passes the condition
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]


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
    target_lawn_mowers: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the lawn mower state condition with the 'all' behavior."""
    other_entity_ids = set(target_lawn_mowers) - {entity_id}

    # Set all lawn mowers, including the tested lawn mower, to the initial state
    for eid in target_lawn_mowers:
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
