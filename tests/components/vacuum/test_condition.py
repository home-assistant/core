"""Test vacuum conditions."""

from typing import Any

import pytest

from homeassistant.components.vacuum import VacuumActivity
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
async def target_vacuums(hass: HomeAssistant) -> list[str]:
    """Create multiple vacuum entities associated with different targets."""
    return (await target_entities(hass, "vacuum"))["included"]


@pytest.mark.parametrize(
    "condition",
    [
        "vacuum.is_cleaning",
        "vacuum.is_docked",
        "vacuum.is_encountering_an_error",
        "vacuum.is_paused",
        "vacuum.is_returning",
    ],
)
async def test_vacuum_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the vacuum conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("vacuum"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="vacuum.is_cleaning",
            target_states=[VacuumActivity.CLEANING],
            other_states=other_states(VacuumActivity.CLEANING),
        ),
        *parametrize_condition_states_any(
            condition="vacuum.is_docked",
            target_states=[VacuumActivity.DOCKED],
            other_states=other_states(VacuumActivity.DOCKED),
        ),
        *parametrize_condition_states_any(
            condition="vacuum.is_encountering_an_error",
            target_states=[VacuumActivity.ERROR],
            other_states=other_states(VacuumActivity.ERROR),
        ),
        *parametrize_condition_states_any(
            condition="vacuum.is_paused",
            target_states=[VacuumActivity.PAUSED],
            other_states=other_states(VacuumActivity.PAUSED),
        ),
        *parametrize_condition_states_any(
            condition="vacuum.is_returning",
            target_states=[VacuumActivity.RETURNING],
            other_states=other_states(VacuumActivity.RETURNING),
        ),
    ],
)
async def test_vacuum_state_condition_behavior_any(
    hass: HomeAssistant,
    target_vacuums: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the vacuum state condition with the 'any' behavior."""
    other_entity_ids = set(target_vacuums) - {entity_id}

    # Set all vacuums, including the tested vacuum, to the initial state
    for eid in target_vacuums:
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

        # Check if changing other vacuums also passes the condition
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("vacuum"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="vacuum.is_cleaning",
            target_states=[VacuumActivity.CLEANING],
            other_states=other_states(VacuumActivity.CLEANING),
        ),
        *parametrize_condition_states_all(
            condition="vacuum.is_docked",
            target_states=[VacuumActivity.DOCKED],
            other_states=other_states(VacuumActivity.DOCKED),
        ),
        *parametrize_condition_states_all(
            condition="vacuum.is_encountering_an_error",
            target_states=[VacuumActivity.ERROR],
            other_states=other_states(VacuumActivity.ERROR),
        ),
        *parametrize_condition_states_all(
            condition="vacuum.is_paused",
            target_states=[VacuumActivity.PAUSED],
            other_states=other_states(VacuumActivity.PAUSED),
        ),
        *parametrize_condition_states_all(
            condition="vacuum.is_returning",
            target_states=[VacuumActivity.RETURNING],
            other_states=other_states(VacuumActivity.RETURNING),
        ),
    ],
)
async def test_vacuum_state_condition_behavior_all(
    hass: HomeAssistant,
    target_vacuums: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the vacuum state condition with the 'all' behavior."""
    other_entity_ids = set(target_vacuums) - {entity_id}

    # Set all vacuums, including the tested vacuum, to the initial state
    for eid in target_vacuums:
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
