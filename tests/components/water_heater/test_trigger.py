"""Test water heater trigger."""

from typing import Any

import pytest

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_PERFORMANCE,
)
from homeassistant.const import (
    ATTR_LABEL_ID,
    ATTR_TEMPERATURE,
    CONF_ENTITY_ID,
    STATE_OFF,
)
from homeassistant.core import HomeAssistant, ServiceCall

from tests.components import (
    TriggerStateDescription,
    arm_trigger,
    parametrize_numerical_attribute_changed_trigger_states,
    parametrize_numerical_attribute_crossed_threshold_trigger_states,
    parametrize_target_entities,
    parametrize_trigger_states,
    set_or_remove_state,
    target_entities,
)

ALL_ON_STATES = [
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_PERFORMANCE,
]


@pytest.fixture
async def target_water_heaters(hass: HomeAssistant) -> list[str]:
    """Create multiple water heater entities associated with different targets."""
    return (await target_entities(hass, "water_heater"))["included"]


@pytest.mark.parametrize(
    "trigger_key",
    [
        "water_heater.target_temperature_changed",
        "water_heater.target_temperature_crossed_threshold",
        "water_heater.turned_off",
        "water_heater.turned_on",
    ],
)
async def test_water_heater_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the water heater triggers are gated by the labs flag."""
    await arm_trigger(hass, trigger_key, None, {ATTR_LABEL_ID: "test_label"})
    assert (
        "Unnamed automation failed to setup triggers and has been disabled: Trigger "
        f"'{trigger_key}' requires the experimental 'New triggers and conditions' "
        "feature to be enabled in Home Assistant Labs settings (feature flag: "
        "'new_triggers_conditions')"
    ) in caplog.text


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="water_heater.turned_off",
            target_states=[STATE_OFF],
            other_states=ALL_ON_STATES,
        ),
        *parametrize_trigger_states(
            trigger="water_heater.turned_on",
            target_states=ALL_ON_STATES,
            other_states=[STATE_OFF],
        ),
    ],
)
async def test_water_heater_state_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_water_heaters: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the water heater state trigger fires when any water heater state changes to a specific state."""
    other_entity_ids = set(target_water_heaters) - {entity_id}

    # Set all water heaters, including the tested water heater, to the initial state
    for eid in target_water_heaters:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, trigger_options, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other water heaters also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_changed_trigger_states(
            "water_heater.target_temperature_changed",
            STATE_ECO,
            ATTR_TEMPERATURE,
        ),
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "water_heater.target_temperature_crossed_threshold",
            STATE_ECO,
            ATTR_TEMPERATURE,
        ),
    ],
)
async def test_water_heater_state_attribute_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_water_heaters: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the water heater state trigger fires when any water heater state changes to a specific state."""
    other_entity_ids = set(target_water_heaters) - {entity_id}

    # Set all water heaters, including the tested water heater, to the initial state
    for eid in target_water_heaters:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, trigger_options, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other water heaters also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="water_heater.turned_off",
            target_states=[STATE_OFF],
            other_states=ALL_ON_STATES,
        ),
        *parametrize_trigger_states(
            trigger="water_heater.turned_on",
            target_states=ALL_ON_STATES,
            other_states=[STATE_OFF],
        ),
    ],
)
async def test_water_heater_state_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_water_heaters: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the water heater state trigger fires when the first water heater changes to a specific state."""
    other_entity_ids = set(target_water_heaters) - {entity_id}

    # Set all water heaters, including the tested water heater, to the initial state
    for eid in target_water_heaters:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(
        hass, trigger, {"behavior": "first"} | trigger_options, trigger_target_config
    )

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other water heaters should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "water_heater.target_temperature_crossed_threshold",
            STATE_ECO,
            ATTR_TEMPERATURE,
        ),
    ],
)
async def test_water_heater_state_attribute_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_water_heaters: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test that the water heater state trigger fires when the first water heater state changes to a specific state."""
    other_entity_ids = set(target_water_heaters) - {entity_id}

    # Set all water heaters, including the tested water heater, to the initial state
    for eid in target_water_heaters:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(
        hass, trigger, {"behavior": "first"} | trigger_options, trigger_target_config
    )

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other water heaters should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="water_heater.turned_off",
            target_states=[STATE_OFF],
            other_states=ALL_ON_STATES,
        ),
        *parametrize_trigger_states(
            trigger="water_heater.turned_on",
            target_states=ALL_ON_STATES,
            other_states=[STATE_OFF],
        ),
    ],
)
async def test_water_heater_state_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_water_heaters: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the water heater state trigger fires when the last water heater changes to a specific state."""
    other_entity_ids = set(target_water_heaters) - {entity_id}

    # Set all water heaters, including the tested water heater, to the initial state
    for eid in target_water_heaters:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(
        hass, trigger, {"behavior": "last"} | trigger_options, trigger_target_config
    )

    for state in states[1:]:
        included_state = state["included"]
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "water_heater.target_temperature_crossed_threshold",
            STATE_ECO,
            ATTR_TEMPERATURE,
        ),
    ],
)
async def test_water_heater_state_attribute_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_water_heaters: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test that the water heater state trigger fires when the last water heater state changes to a specific state."""
    other_entity_ids = set(target_water_heaters) - {entity_id}

    # Set all water heaters, including the tested water heater, to the initial state
    for eid in target_water_heaters:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(
        hass, trigger, {"behavior": "last"} | trigger_options, trigger_target_config
    )

    for state in states[1:]:
        included_state = state["included"]
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()
