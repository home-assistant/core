"""Test fan conditions."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.components import (
    ConditionStateDescription,
    create_target_condition,
    help_test_condition_gated_by_labs_flag,
    parametrize_condition_states,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
async def target_fans(hass: HomeAssistant) -> list[str]:
    """Create multiple fan entities associated with different targets."""
    return (await target_entities(hass, "fan"))["included"]


@pytest.fixture
async def target_switches(hass: HomeAssistant) -> list[str]:
    """Create multiple switch entities associated with different targets."""
    return (await target_entities(hass, "switch"))["included"]


@pytest.fixture(name="enable_experimental_triggers_conditions")
def enable_experimental_triggers_conditions() -> Generator[None]:
    """Enable experimental triggers and conditions."""
    with patch(
        "homeassistant.components.labs.async_is_preview_feature_enabled",
        return_value=True,
    ):
        yield


@pytest.mark.parametrize(
    "condition",
    [
        "fan.is_off",
        "fan.is_on",
    ],
)
async def test_fan_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the fan conditions are gated by the labs flag."""
    await help_test_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("fan"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states(
            condition="fan.is_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_condition_states(
            condition="fan.is_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_fan_state_condition_behavior_any(
    hass: HomeAssistant,
    target_fans: list[str],
    target_switches: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the fan state condition with the 'any' behavior."""
    other_entity_ids = set(target_fans) - {entity_id}

    # Set all fans, including the tested fan, to the initial state
    for eid in target_fans:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="any",
    )

    # Set state for switches to ensure that they don't impact the condition
    for state in states:
        for eid in target_switches:
            set_or_remove_state(hass, eid, state["included"])
            await hass.async_block_till_done()
            assert condition(hass) is False

    for state in states:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]

        # Check if changing other fans also passes the condition
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("fan"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states(
            condition="fan.is_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_condition_states(
            condition="fan.is_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_fan_state_condition_behavior_all(
    hass: HomeAssistant,
    target_fans: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the fan state condition with the 'all' behavior."""
    # Set state for two switches to ensure that they don't impact the condition
    hass.states.async_set("switch.label_switch_1", STATE_OFF)
    hass.states.async_set("switch.label_switch_2", STATE_ON)

    other_entity_ids = set(target_fans) - {entity_id}

    # Set all fans, including the tested fan, to the initial state
    for eid in target_fans:
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
        # The condition passes if all entities are either in a target state or invalid
        assert condition(hass) == (
            (not state["state_valid"])
            or (state["condition_true"] and entities_in_target == 1)
        )

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()

        # The condition passes if all entities are either in a target state or invalid
        assert condition(hass) == (
            (not state["state_valid"]) or state["condition_true"]
        )
