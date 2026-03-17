"""Test climate trigger."""

from contextlib import AbstractContextManager, nullcontext as does_not_raise
from typing import Any

import pytest
import voluptuous as vol

from homeassistant.components.climate.const import (
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    HVACAction,
    HVACMode,
)
from homeassistant.components.climate.trigger import CONF_HVAC_MODE
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ENTITY_ID,
    CONF_OPTIONS,
    CONF_TARGET,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.trigger import async_validate_trigger_config

from tests.components import (
    TriggerStateDescription,
    arm_trigger,
    assert_trigger_behavior_any,
    assert_trigger_gated_by_labs_flag,
    other_states,
    parametrize_numerical_attribute_changed_trigger_states,
    parametrize_numerical_attribute_crossed_threshold_trigger_states,
    parametrize_target_entities,
    parametrize_trigger_states,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture
async def target_climates(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple climate entities associated with different targets."""
    return await target_entities(hass, "climate")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "climate.hvac_mode_changed",
        "climate.target_humidity_changed",
        "climate.target_humidity_crossed_threshold",
        "climate.target_temperature_changed",
        "climate.target_temperature_crossed_threshold",
        "climate.turned_off",
        "climate.turned_on",
        "climate.started_heating",
    ],
)
async def test_climate_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the climate triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "expected_result"),
    [
        # Test validating climate.hvac_mode_changed
        # Valid configurations
        (
            "climate.hvac_mode_changed",
            {CONF_HVAC_MODE: ["heat", "cool"]},
            does_not_raise(),
        ),
        (
            "climate.hvac_mode_changed",
            {CONF_HVAC_MODE: "heat"},
            does_not_raise(),
        ),
        # Invalid configurations
        (
            "climate.hvac_mode_changed",
            # Empty hvac_mode list
            {CONF_HVAC_MODE: []},
            pytest.raises(vol.Invalid),
        ),
        (
            "climate.hvac_mode_changed",
            # Missing CONF_HVAC_MODE
            {},
            pytest.raises(vol.Invalid),
        ),
        (
            "climate.hvac_mode_changed",
            {CONF_HVAC_MODE: ["invalid_mode"]},
            pytest.raises(vol.Invalid),
        ),
    ],
)
async def test_climate_trigger_validation(
    hass: HomeAssistant,
    trigger: str,
    trigger_options: dict[str, Any],
    expected_result: AbstractContextManager,
) -> None:
    """Test climate trigger config validation."""
    with expected_result:
        await async_validate_trigger_config(
            hass,
            [
                {
                    "platform": trigger,
                    CONF_TARGET: {CONF_ENTITY_ID: "climate.test_climate"},
                    CONF_OPTIONS: trigger_options,
                }
            ],
        )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="climate.hvac_mode_changed",
            trigger_options={CONF_HVAC_MODE: ["heat", "cool"]},
            target_states=[HVACMode.HEAT, HVACMode.COOL],
            other_states=other_states([HVACMode.HEAT, HVACMode.COOL]),
        ),
        *parametrize_trigger_states(
            trigger="climate.turned_off",
            target_states=[HVACMode.OFF],
            other_states=other_states(HVACMode.OFF),
        ),
        *parametrize_trigger_states(
            trigger="climate.turned_on",
            target_states=[
                HVACMode.AUTO,
                HVACMode.COOL,
                HVACMode.DRY,
                HVACMode.FAN_ONLY,
                HVACMode.HEAT,
                HVACMode.HEAT_COOL,
            ],
            other_states=[
                HVACMode.OFF,
            ],
        ),
    ],
)
async def test_climate_state_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_climates: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the climate state trigger fires when any climate state changes to a specific state."""
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
        target_entities=target_climates,
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
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_changed_trigger_states(
            "climate.target_humidity_changed", HVACMode.AUTO, ATTR_HUMIDITY
        ),
        *parametrize_numerical_attribute_changed_trigger_states(
            "climate.target_temperature_changed", HVACMode.AUTO, ATTR_TEMPERATURE
        ),
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "climate.target_humidity_crossed_threshold", HVACMode.AUTO, ATTR_HUMIDITY
        ),
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "climate.target_temperature_crossed_threshold",
            HVACMode.AUTO,
            ATTR_TEMPERATURE,
        ),
        *parametrize_trigger_states(
            trigger="climate.started_cooling",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.COOLING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
        *parametrize_trigger_states(
            trigger="climate.started_drying",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.DRYING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
        *parametrize_trigger_states(
            trigger="climate.started_heating",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.HEATING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
    ],
)
async def test_climate_state_attribute_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_climates: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the climate state trigger fires when any climate state changes to a specific state."""
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
        target_entities=target_climates,
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
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="climate.hvac_mode_changed",
            trigger_options={CONF_HVAC_MODE: ["heat", "cool"]},
            target_states=[HVACMode.HEAT, HVACMode.COOL],
            other_states=other_states([HVACMode.HEAT, HVACMode.COOL]),
        ),
        *parametrize_trigger_states(
            trigger="climate.turned_off",
            target_states=[HVACMode.OFF],
            other_states=other_states(HVACMode.OFF),
        ),
        *parametrize_trigger_states(
            trigger="climate.turned_on",
            target_states=[
                HVACMode.AUTO,
                HVACMode.COOL,
                HVACMode.DRY,
                HVACMode.FAN_ONLY,
                HVACMode.HEAT,
                HVACMode.HEAT_COOL,
            ],
            other_states=[
                HVACMode.OFF,
            ],
        ),
    ],
)
async def test_climate_state_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_climates: dict[str, list[str]],
    trigger_target_config: dict,
    entities_in_target: int,
    entity_id: str,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the climate state trigger fires when the first climate changes to a specific state."""
    other_entity_ids = set(target_climates["included"]) - {entity_id}

    # Set all climates, including the tested climate, to the initial state
    for eid in target_climates["included"]:
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

        # Triggering other climates should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "climate.target_humidity_crossed_threshold", HVACMode.AUTO, ATTR_HUMIDITY
        ),
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "climate.target_temperature_crossed_threshold",
            HVACMode.AUTO,
            ATTR_TEMPERATURE,
        ),
        *parametrize_trigger_states(
            trigger="climate.started_cooling",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.COOLING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
        *parametrize_trigger_states(
            trigger="climate.started_drying",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.DRYING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
        *parametrize_trigger_states(
            trigger="climate.started_heating",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.HEATING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
    ],
)
async def test_climate_state_attribute_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_climates: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test that the climate state trigger fires when the first climate state changes to a specific state."""
    other_entity_ids = set(target_climates["included"]) - {entity_id}

    # Set all climates, including the tested climate, to the initial state
    for eid in target_climates["included"]:
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

        # Triggering other climates should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="climate.hvac_mode_changed",
            trigger_options={CONF_HVAC_MODE: ["heat", "cool"]},
            target_states=[HVACMode.HEAT, HVACMode.COOL],
            other_states=other_states([HVACMode.HEAT, HVACMode.COOL]),
        ),
        *parametrize_trigger_states(
            trigger="climate.turned_off",
            target_states=[HVACMode.OFF],
            other_states=other_states(HVACMode.OFF),
        ),
        *parametrize_trigger_states(
            trigger="climate.turned_on",
            target_states=[
                HVACMode.AUTO,
                HVACMode.COOL,
                HVACMode.DRY,
                HVACMode.FAN_ONLY,
                HVACMode.HEAT,
                HVACMode.HEAT_COOL,
            ],
            other_states=[
                HVACMode.OFF,
            ],
        ),
    ],
)
async def test_climate_state_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_climates: dict[str, list[str]],
    trigger_target_config: dict,
    entities_in_target: int,
    entity_id: str,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the climate state trigger fires when the last climate changes to a specific state."""
    other_entity_ids = set(target_climates["included"]) - {entity_id}

    # Set all climates, including the tested climate, to the initial state
    for eid in target_climates["included"]:
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
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "climate.target_humidity_crossed_threshold", HVACMode.AUTO, ATTR_HUMIDITY
        ),
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "climate.target_temperature_crossed_threshold",
            HVACMode.AUTO,
            ATTR_TEMPERATURE,
        ),
        *parametrize_trigger_states(
            trigger="climate.started_cooling",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.COOLING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
        *parametrize_trigger_states(
            trigger="climate.started_drying",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.DRYING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
        *parametrize_trigger_states(
            trigger="climate.started_heating",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.HEATING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
    ],
)
async def test_climate_state_attribute_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_climates: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test that the climate state trigger fires when the last climate state changes to a specific state."""
    other_entity_ids = set(target_climates["included"]) - {entity_id}

    # Set all climates, including the tested climate, to the initial state
    for eid in target_climates["included"]:
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
