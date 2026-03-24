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
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, STATE_ON, UnitOfTemperature
from homeassistant.core import HomeAssistant, ServiceCall

from tests.components.common import (
    TriggerStateDescription,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_behavior_last,
    assert_trigger_gated_by_labs_flag,
    parametrize_numerical_attribute_changed_trigger_states,
    parametrize_numerical_attribute_crossed_threshold_trigger_states,
    parametrize_target_entities,
    parametrize_trigger_states,
    target_entities,
)

ALL_ON_STATES = [
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_ON,
    STATE_PERFORMANCE,
]

_TEMPERATURE_TRIGGER_OPTIONS = {"unit": UnitOfTemperature.CELSIUS}


@pytest.fixture
async def target_water_heaters(hass: HomeAssistant) -> list[str]:
    """Create multiple water heater entities associated with different targets."""
    return await target_entities(hass, "water_heater")


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
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


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
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
        target_entities=target_water_heaters,
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
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_changed_trigger_states(
            "water_heater.target_temperature_changed",
            STATE_ECO,
            ATTR_TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
        ),
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "water_heater.target_temperature_crossed_threshold",
            STATE_ECO,
            ATTR_TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
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
    """Test that the water heater target temperature attribute triggers fire when any water heater's target temperature changes or crosses a threshold."""
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
        target_entities=target_water_heaters,
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
    await assert_trigger_behavior_first(
        hass,
        service_calls=service_calls,
        target_entities=target_water_heaters,
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
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "water_heater.target_temperature_crossed_threshold",
            STATE_ECO,
            ATTR_TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
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
    """Test that the water heater attribute threshold trigger fires when the first water heater's target temperature crosses the configured threshold."""
    await assert_trigger_behavior_first(
        hass,
        service_calls=service_calls,
        target_entities=target_water_heaters,
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
    await assert_trigger_behavior_last(
        hass,
        service_calls=service_calls,
        target_entities=target_water_heaters,
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
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "water_heater.target_temperature_crossed_threshold",
            STATE_ECO,
            ATTR_TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
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
    """Test that the water heater trigger fires when the last water heater's target temperature crosses the configured threshold."""
    await assert_trigger_behavior_last(
        hass,
        service_calls=service_calls,
        target_entities=target_water_heaters,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )
