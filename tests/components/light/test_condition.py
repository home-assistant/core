"""Test light conditions."""

from typing import Any

import pytest

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    create_target_condition,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)


def parametrize_brightness_condition_states_any(
    condition: str, state: str, attribute: str
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize above/below threshold test cases for brightness conditions.

    Note: The brightness in the condition configuration is in percentage (0-100) scale,
    the underlying attribute in the state is in uint8 (0-255) scale.
    """
    return [
        *parametrize_condition_states_any(
            condition=condition,
            condition_options={"threshold": {"type": "above", "value": {"number": 10}}},
            target_states=[
                (state, {attribute: 128}),
                (state, {attribute: 255}),
            ],
            other_states=[
                (state, {attribute: 0}),
                (state, {attribute: None}),
            ],
        ),
        *parametrize_condition_states_any(
            condition=condition,
            condition_options={"threshold": {"type": "below", "value": {"number": 90}}},
            target_states=[
                (state, {attribute: 0}),
                (state, {attribute: 128}),
            ],
            other_states=[
                (state, {attribute: 255}),
                (state, {attribute: None}),
            ],
        ),
        *parametrize_condition_states_any(
            condition=condition,
            condition_options={
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 10},
                    "value_max": {"number": 90},
                }
            },
            target_states=[
                (state, {attribute: 128}),
                (state, {attribute: 153}),
            ],
            other_states=[
                (state, {attribute: 0}),
                (state, {attribute: 255}),
                (state, {attribute: None}),
            ],
        ),
    ]


def parametrize_brightness_condition_states_all(
    condition: str, state: str, attribute: str
) -> list[tuple[str, dict[str, Any], list[ConditionStateDescription]]]:
    """Parametrize above/below threshold test cases for brightness conditions with 'all' behavior.

    Note: The brightness in the condition configuration is in percentage (0-100) scale,
    the underlying attribute in the state is in uint8 (0-255) scale.
    """
    return [
        *parametrize_condition_states_all(
            condition=condition,
            condition_options={"threshold": {"type": "above", "value": {"number": 10}}},
            target_states=[
                (state, {attribute: 128}),
                (state, {attribute: 255}),
            ],
            other_states=[
                (state, {attribute: 0}),
                (state, {attribute: None}),
            ],
        ),
        *parametrize_condition_states_all(
            condition=condition,
            condition_options={"threshold": {"type": "below", "value": {"number": 90}}},
            target_states=[
                (state, {attribute: 0}),
                (state, {attribute: 128}),
            ],
            other_states=[
                (state, {attribute: 255}),
                (state, {attribute: None}),
            ],
        ),
        *parametrize_condition_states_all(
            condition=condition,
            condition_options={
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 10},
                    "value_max": {"number": 90},
                }
            },
            target_states=[
                (state, {attribute: 128}),
                (state, {attribute: 153}),
            ],
            other_states=[
                (state, {attribute: 0}),
                (state, {attribute: 255}),
                (state, {attribute: None}),
            ],
        ),
    ]


@pytest.fixture
async def target_lights(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple light entities associated with different targets."""
    return await target_entities(hass, "light")


@pytest.fixture
async def target_switches(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple switch entities associated with different targets.

    Note: The switches are used to ensure that only light entities are considered
    in the condition evaluation and not other toggle entities.
    """
    return await target_entities(hass, "switch")


@pytest.mark.parametrize(
    "condition",
    [
        "light.is_brightness",
        "light.is_off",
        "light.is_on",
    ],
)
async def test_light_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the light conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("light"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="light.is_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_condition_states_any(
            condition="light.is_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_light_state_condition_behavior_any(
    hass: HomeAssistant,
    target_lights: dict[str, list[str]],
    target_switches: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the light state condition with the 'any' behavior."""
    other_entity_ids = set(target_lights["included_entities"]) - {entity_id}

    # Set all lights, including the tested light, to the initial state
    for eid in target_lights["included_entities"]:
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

        # Check if changing other lights also passes the condition
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("light"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="light.is_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_condition_states_all(
            condition="light.is_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_light_state_condition_behavior_all(
    hass: HomeAssistant,
    target_lights: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the light state condition with the 'all' behavior."""
    # Set state for two switches to ensure that they don't impact the condition
    hass.states.async_set("switch.label_switch_1", STATE_OFF)
    hass.states.async_set("switch.label_switch_2", STATE_ON)

    other_entity_ids = set(target_lights["included_entities"]) - {entity_id}

    # Set all lights, including the tested light, to the initial state
    for eid in target_lights["included_entities"]:
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


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("light"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_brightness_condition_states_any(
            "light.is_brightness", STATE_ON, ATTR_BRIGHTNESS
        ),
    ],
)
async def test_light_brightness_condition_behavior_any(
    hass: HomeAssistant,
    target_lights: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the light brightness condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_lights,
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
    parametrize_target_entities("light"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_brightness_condition_states_all(
            "light.is_brightness", STATE_ON, ATTR_BRIGHTNESS
        ),
    ],
)
async def test_light_brightness_condition_behavior_all(
    hass: HomeAssistant,
    target_lights: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the light brightness condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_lights,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
