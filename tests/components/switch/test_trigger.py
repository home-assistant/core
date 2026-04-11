"""Test switch triggers."""

from typing import Any

import pytest

from homeassistant.components.switch import DOMAIN
from homeassistant.const import CONF_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.components.common import (
    TriggerStateDescription,
    arm_trigger,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_behavior_last,
    assert_trigger_gated_by_labs_flag,
    parametrize_target_entities,
    parametrize_trigger_states,
    target_entities,
)

TRIGGER_STATES = [
    *parametrize_trigger_states(
        trigger="switch.turned_off",
        target_states=[STATE_OFF],
        other_states=[STATE_ON],
    ),
    *parametrize_trigger_states(
        trigger="switch.turned_on",
        target_states=[STATE_ON],
        other_states=[STATE_OFF],
    ),
]


@pytest.fixture
async def target_switches(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple switch entities associated with different targets."""
    return await target_entities(hass, DOMAIN)


@pytest.fixture
async def target_input_booleans(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple input_boolean entities associated with different targets."""
    return await target_entities(hass, "input_boolean")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "switch.turned_off",
        "switch.turned_on",
    ],
)
async def test_switch_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the switch triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


# --- Switch domain tests ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    TRIGGER_STATES,
)
async def test_switch_state_trigger_behavior_any(
    hass: HomeAssistant,
    target_switches: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the switch state trigger fires when any switch state changes to a specific state."""
    await assert_trigger_behavior_any(
        hass,
        target_entities=target_switches,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    TRIGGER_STATES,
)
async def test_switch_state_trigger_behavior_first(
    hass: HomeAssistant,
    target_switches: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the switch state trigger fires when the first switch changes to a specific state."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_switches,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    TRIGGER_STATES,
)
async def test_switch_state_trigger_behavior_last(
    hass: HomeAssistant,
    target_switches: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the switch state trigger fires when the last switch changes to a specific state."""
    await assert_trigger_behavior_last(
        hass,
        target_entities=target_switches,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


# --- Input boolean domain tests ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("input_boolean"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    TRIGGER_STATES,
)
async def test_input_boolean_state_trigger_behavior_any(
    hass: HomeAssistant,
    target_input_booleans: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the switch trigger fires when any input_boolean state changes."""
    await assert_trigger_behavior_any(
        hass,
        target_entities=target_input_booleans,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("input_boolean"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    TRIGGER_STATES,
)
async def test_input_boolean_state_trigger_behavior_first(
    hass: HomeAssistant,
    target_input_booleans: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the switch trigger fires when the first input_boolean changes."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_input_booleans,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("input_boolean"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    TRIGGER_STATES,
)
async def test_input_boolean_state_trigger_behavior_last(
    hass: HomeAssistant,
    target_input_booleans: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the switch trigger fires when the last input_boolean changes."""
    await assert_trigger_behavior_last(
        hass,
        target_entities=target_input_booleans,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


# --- Cross-domain test ---


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_switch_trigger_fires_for_both_domains(
    hass: HomeAssistant,
) -> None:
    """Test that the switch trigger fires for both switch and input_boolean entities."""
    calls: list[str] = []
    entity_id_switch = "switch.test_switch"
    entity_id_input_boolean = "input_boolean.test_input_boolean"

    hass.states.async_set(entity_id_switch, STATE_OFF)
    hass.states.async_set(entity_id_input_boolean, STATE_OFF)
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        "switch.turned_on",
        {},
        {CONF_ENTITY_ID: [entity_id_switch, entity_id_input_boolean]},
        calls,
    )

    # switch entity changes - should trigger
    hass.states.async_set(entity_id_switch, STATE_ON)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0] == entity_id_switch
    calls.clear()

    # input_boolean entity changes - should also trigger
    hass.states.async_set(entity_id_input_boolean, STATE_ON)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0] == entity_id_input_boolean
    calls.clear()
