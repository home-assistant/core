"""Test select conditions."""

from contextlib import AbstractContextManager, nullcontext as does_not_raise
from typing import Any

import pytest
import voluptuous as vol

from homeassistant.components.select.condition import CONF_OPTION
from homeassistant.const import CONF_ENTITY_ID, CONF_OPTIONS, CONF_TARGET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import async_validate_condition_config

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    create_target_condition,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    target_entities,
)


@pytest.fixture
async def target_selects(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple select entities associated with different targets."""
    return await target_entities(hass, "select")


@pytest.fixture
async def target_input_selects(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple input_select entities associated with different targets."""
    return await target_entities(hass, "input_select")


@pytest.mark.parametrize(
    "condition",
    ["select.is_option_selected"],
)
async def test_select_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the select conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("select"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_condition_states_any(
        condition="select.is_option_selected",
        condition_options={CONF_OPTION: ["option_a", "option_b"]},
        target_states=["option_a", "option_b"],
        other_states=["option_c"],
    ),
)
async def test_select_condition_behavior_any(
    hass: HomeAssistant,
    target_selects: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the select condition with 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_selects,
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
    parametrize_target_entities("select"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_condition_states_all(
        condition="select.is_option_selected",
        condition_options={CONF_OPTION: ["option_a", "option_b"]},
        target_states=["option_a", "option_b"],
        other_states=["option_c"],
    ),
)
async def test_select_condition_behavior_all(
    hass: HomeAssistant,
    target_selects: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the select condition with 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_selects,
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
    parametrize_target_entities("input_select"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_condition_states_any(
        condition="select.is_option_selected",
        condition_options={CONF_OPTION: ["option_a", "option_b"]},
        target_states=["option_a", "option_b"],
        other_states=["option_c"],
    ),
)
async def test_input_select_condition_behavior_any(
    hass: HomeAssistant,
    target_input_selects: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the select condition with input_select entities and 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_input_selects,
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
    parametrize_target_entities("input_select"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_condition_states_all(
        condition="select.is_option_selected",
        condition_options={CONF_OPTION: ["option_a", "option_b"]},
        target_states=["option_a", "option_b"],
        other_states=["option_c"],
    ),
)
async def test_input_select_condition_behavior_all(
    hass: HomeAssistant,
    target_input_selects: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the select condition with input_select entities and 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_input_selects,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


# --- Cross-domain test ---


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_select_condition_evaluates_both_domains(
    hass: HomeAssistant,
) -> None:
    """Test that the select condition evaluates both select and input_select entities."""
    entity_id_select = "select.test_select"
    entity_id_input_select = "input_select.test_input_select"

    hass.states.async_set(entity_id_select, "option_a")
    hass.states.async_set(entity_id_input_select, "option_a")
    await hass.async_block_till_done()

    cond = await create_target_condition(
        hass,
        condition="select.is_option_selected",
        target={CONF_ENTITY_ID: [entity_id_select, entity_id_input_select]},
        behavior="any",
        condition_options={CONF_OPTION: ["option_a", "option_b"]},
    )

    assert cond(hass) is True

    # Set one to a non-matching option - "any" behavior should still pass
    hass.states.async_set(entity_id_select, "option_c")
    await hass.async_block_till_done()

    assert cond(hass) is True

    # Set both to non-matching options
    hass.states.async_set(entity_id_input_select, "option_c")
    await hass.async_block_till_done()

    assert cond(hass) is False


# --- Schema validation tests ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition", "condition_options", "expected_result"),
    [
        # Valid configurations
        (
            "select.is_option_selected",
            {CONF_OPTION: ["option_a", "option_b"]},
            does_not_raise(),
        ),
        (
            "select.is_option_selected",
            {CONF_OPTION: "option_a"},
            does_not_raise(),
        ),
        # Invalid configurations
        (
            "select.is_option_selected",
            # Empty option list
            {CONF_OPTION: []},
            pytest.raises(vol.Invalid),
        ),
        (
            "select.is_option_selected",
            # Missing CONF_OPTION
            {},
            pytest.raises(vol.Invalid),
        ),
    ],
)
async def test_select_is_option_selected_condition_validation(
    hass: HomeAssistant,
    condition: str,
    condition_options: dict[str, Any],
    expected_result: AbstractContextManager,
) -> None:
    """Test select is_option_selected condition config validation."""
    with expected_result:
        await async_validate_condition_config(
            hass,
            {
                "condition": condition,
                CONF_TARGET: {CONF_ENTITY_ID: "select.test"},
                CONF_OPTIONS: condition_options,
            },
        )
