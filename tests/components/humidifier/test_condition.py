"""Test humidifier conditions."""

from typing import Any

import pytest

from homeassistant.components.humidifier.const import ATTR_ACTION, HumidifierAction
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.components import (
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
async def target_humidifiers(hass: HomeAssistant) -> list[str]:
    """Create multiple humidifier entities associated with different targets."""
    return (await target_entities(hass, "humidifier"))["included"]


@pytest.mark.parametrize(
    "condition",
    [
        "humidifier.is_off",
        "humidifier.is_on",
        "humidifier.is_drying",
        "humidifier.is_humidifying",
    ],
)
async def test_humidifier_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the humidifier conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="humidifier.is_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
        *parametrize_condition_states_any(
            condition="humidifier.is_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
    ],
)
async def test_humidifier_state_condition_behavior_any(
    hass: HomeAssistant,
    target_humidifiers: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the humidifier state condition with the 'any' behavior."""
    other_entity_ids = set(target_humidifiers) - {entity_id}

    # Set all humidifiers, including the tested humidifier, to the initial state
    for eid in target_humidifiers:
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

        # Check if changing other humidifiers also passes the condition
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="humidifier.is_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
        *parametrize_condition_states_all(
            condition="humidifier.is_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
    ],
)
async def test_humidifier_state_condition_behavior_all(
    hass: HomeAssistant,
    target_humidifiers: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the humidifier state condition with the 'all' behavior."""
    other_entity_ids = set(target_humidifiers) - {entity_id}

    # Set all humidifiers, including the tested humidifier, to the initial state
    for eid in target_humidifiers:
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


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="humidifier.is_drying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.DRYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
        *parametrize_condition_states_any(
            condition="humidifier.is_humidifying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.HUMIDIFYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
    ],
)
async def test_humidifier_attribute_condition_behavior_any(
    hass: HomeAssistant,
    target_humidifiers: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the humidifier attribute condition with the 'any' behavior."""
    other_entity_ids = set(target_humidifiers) - {entity_id}

    # Set all humidifiers, including the tested humidifier, to the initial state
    for eid in target_humidifiers:
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

        # Check if changing other humidifiers also passes the condition
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="humidifier.is_drying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.DRYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
        *parametrize_condition_states_all(
            condition="humidifier.is_humidifying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.HUMIDIFYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
    ],
)
async def test_humidifier_attribute_condition_behavior_all(
    hass: HomeAssistant,
    target_humidifiers: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the humidifier attribute condition with the 'all' behavior."""
    other_entity_ids = set(target_humidifiers) - {entity_id}

    # Set all humidifiers, including the tested humidifier, to the initial state
    for eid in target_humidifiers:
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
