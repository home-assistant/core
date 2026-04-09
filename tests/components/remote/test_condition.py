"""Test remote conditions."""

from typing import Any

import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_gated_by_labs_flag,
    create_target_condition,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture
async def target_remotes(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple remote entities associated with different targets."""
    return await target_entities(hass, "remote")


@pytest.fixture
async def target_switches(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple switch entities associated with different targets.

    Note: The switches are used to ensure that only remote entities are considered
    in the condition evaluation and not other toggle entities.
    """
    return await target_entities(hass, "switch")


@pytest.mark.parametrize(
    "condition",
    [
        "remote.is_off",
        "remote.is_on",
    ],
)
async def test_remote_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the remote conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("remote"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="remote.is_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_condition_states_any(
            condition="remote.is_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_remote_state_condition_behavior_any(
    hass: HomeAssistant,
    target_remotes: dict[str, list[str]],
    target_switches: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the remote state condition with the 'any' behavior."""
    other_entity_ids = set(target_remotes["included_entities"]) - {entity_id}

    # Set all remotes, including the tested remote, to the initial state
    for eid in target_remotes["included_entities"]:
        set_or_remove_state(hass, eid, states[0]["included_state"])
        await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="any",
    )

    # Set state for switches to ensure that they don't impact the condition
    for state in states:
        for eid in target_switches["included_entities"]:
            set_or_remove_state(hass, eid, state["included_state"])
            await hass.async_block_till_done()
            assert condition(hass) is False

    for state in states:
        included_state = state["included_state"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]

        # Check if changing other remotes also passes the condition
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("remote"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="remote.is_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_condition_states_all(
            condition="remote.is_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_remote_state_condition_behavior_all(
    hass: HomeAssistant,
    target_remotes: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the remote state condition with the 'all' behavior."""
    # Set state for two switches to ensure that they don't impact the condition
    hass.states.async_set("switch.label_switch_1", STATE_OFF)
    hass.states.async_set("switch.label_switch_2", STATE_ON)

    other_entity_ids = set(target_remotes["included_entities"]) - {entity_id}

    # Set all remotes, including the tested remote, to the initial state
    for eid in target_remotes["included_entities"]:
        set_or_remove_state(hass, eid, states[0]["included_state"])
        await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="all",
    )

    for state in states:
        included_state = state["included_state"]

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert condition(hass) == state["condition_true_first_entity"]

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()

        assert condition(hass) == state["condition_true"]
