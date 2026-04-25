"""Test switch conditions."""

from typing import Any

import pytest

from homeassistant.const import CONF_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    assert_condition_options_supported,
    create_target_condition,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    target_entities,
)


@pytest.fixture
async def target_switches(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple switch entities associated with different targets."""
    return await target_entities(hass, "switch", domain_excluded="light")


@pytest.fixture
async def target_input_booleans(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple input_boolean entities associated with different targets."""
    return await target_entities(hass, "input_boolean")


@pytest.mark.parametrize(
    "condition",
    [
        "switch.is_off",
        "switch.is_on",
    ],
)
async def test_switch_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the switch conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("switch.is_off", {}, True, True),
        ("switch.is_on", {}, True, True),
    ],
)
async def test_switch_condition_options_validation(
    hass: HomeAssistant,
    condition_key: str,
    base_options: dict[str, Any] | None,
    supports_behavior: bool,
    supports_duration: bool,
) -> None:
    """Test that switch conditions support the expected options."""
    await assert_condition_options_supported(
        hass,
        condition_key,
        base_options,
        supports_behavior=supports_behavior,
        supports_duration=supports_duration,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("switch"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="switch.is_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            excluded_entities_from_other_domain=True,
        ),
        *parametrize_condition_states_any(
            condition="switch.is_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            excluded_entities_from_other_domain=True,
        ),
    ],
)
async def test_switch_state_condition_behavior_any(
    hass: HomeAssistant,
    target_switches: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the switch state condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_switches,
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
    parametrize_target_entities("switch"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="switch.is_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            excluded_entities_from_other_domain=True,
        ),
        *parametrize_condition_states_all(
            condition="switch.is_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            excluded_entities_from_other_domain=True,
        ),
    ],
)
async def test_switch_state_condition_behavior_all(
    hass: HomeAssistant,
    target_switches: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the switch state condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_switches,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


CONDITION_STATES = [
    *parametrize_condition_states_any(
        condition="switch.is_on",
        target_states=[STATE_ON],
        other_states=[STATE_OFF],
    ),
    *parametrize_condition_states_any(
        condition="switch.is_off",
        target_states=[STATE_OFF],
        other_states=[STATE_ON],
    ),
]

CONDITION_STATES_ALL = [
    *parametrize_condition_states_all(
        condition="switch.is_on",
        target_states=[STATE_ON],
        other_states=[STATE_OFF],
    ),
    *parametrize_condition_states_all(
        condition="switch.is_off",
        target_states=[STATE_OFF],
        other_states=[STATE_ON],
    ),
]


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("input_boolean"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    CONDITION_STATES,
)
async def test_input_boolean_state_condition_behavior_any(
    hass: HomeAssistant,
    target_input_booleans: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the switch condition fires for input_boolean with 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_input_booleans,
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
    parametrize_target_entities("input_boolean"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    CONDITION_STATES_ALL,
)
async def test_input_boolean_state_condition_behavior_all(
    hass: HomeAssistant,
    target_input_booleans: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the switch condition fires for input_boolean with 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_input_booleans,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_switch_condition_evaluates_both_domains(
    hass: HomeAssistant,
) -> None:
    """Test that the switch condition evaluates both switch and input_boolean entities."""
    entity_id_switch = "switch.test_switch"
    entity_id_input_boolean = "input_boolean.test_input_boolean"

    hass.states.async_set(entity_id_switch, STATE_OFF)
    hass.states.async_set(entity_id_input_boolean, STATE_OFF)
    await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition="switch.is_on",
        target={CONF_ENTITY_ID: [entity_id_switch, entity_id_input_boolean]},
        behavior="any",
    )

    # Both off - condition should be false
    assert condition(hass) is False

    # switch entity turns on - condition should be true
    hass.states.async_set(entity_id_switch, STATE_ON)
    await hass.async_block_till_done()
    assert condition(hass) is True

    # Reset switch, turn on input_boolean - condition should still be true
    hass.states.async_set(entity_id_switch, STATE_OFF)
    hass.states.async_set(entity_id_input_boolean, STATE_ON)
    await hass.async_block_till_done()
    assert condition(hass) is True
