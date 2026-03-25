"""Test power trigger."""

from typing import Any

import pytest

from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfPower
from homeassistant.core import HomeAssistant

from tests.components.common import (
    TriggerStateDescription,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_behavior_last,
    assert_trigger_gated_by_labs_flag,
    parametrize_numerical_state_value_changed_trigger_states,
    parametrize_numerical_state_value_crossed_threshold_trigger_states,
    parametrize_target_entities,
    target_entities,
)

_POWER_UNIT_ATTRIBUTES = {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT}


@pytest.fixture
async def target_numbers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple number entities associated with different targets."""
    return await target_entities(hass, "number")


@pytest.fixture
async def target_sensors(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple sensor entities associated with different targets."""
    return await target_entities(hass, "sensor")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "power.changed",
        "power.crossed_threshold",
    ],
)
async def test_power_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the power triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_state_value_changed_trigger_states(
            "power.changed",
            device_class=SensorDeviceClass.POWER,
            threshold_unit=UnitOfPower.WATT,
            unit_attributes=_POWER_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "power.crossed_threshold",
            device_class=SensorDeviceClass.POWER,
            threshold_unit=UnitOfPower.WATT,
            unit_attributes=_POWER_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_power_trigger_sensor_behavior_any(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test power trigger fires for sensor entities with device_class power."""
    await assert_trigger_behavior_any(
        hass,
        target_entities=target_sensors,
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
    parametrize_target_entities("sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "power.crossed_threshold",
            device_class=SensorDeviceClass.POWER,
            threshold_unit=UnitOfPower.WATT,
            unit_attributes=_POWER_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_power_trigger_sensor_crossed_threshold_behavior_first(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test power crossed_threshold trigger fires on the first sensor state change."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_sensors,
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
    parametrize_target_entities("sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "power.crossed_threshold",
            device_class=SensorDeviceClass.POWER,
            threshold_unit=UnitOfPower.WATT,
            unit_attributes=_POWER_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_power_trigger_sensor_crossed_threshold_behavior_last(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test power crossed_threshold trigger fires when the last sensor changes state."""
    await assert_trigger_behavior_last(
        hass,
        target_entities=target_sensors,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


# --- Number entity tests ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("number"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_state_value_changed_trigger_states(
            "power.changed",
            device_class=NumberDeviceClass.POWER,
            threshold_unit=UnitOfPower.WATT,
            unit_attributes=_POWER_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "power.crossed_threshold",
            device_class=NumberDeviceClass.POWER,
            threshold_unit=UnitOfPower.WATT,
            unit_attributes=_POWER_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_power_trigger_number_behavior_any(
    hass: HomeAssistant,
    target_numbers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test power trigger fires for number entities with device_class power."""
    await assert_trigger_behavior_any(
        hass,
        target_entities=target_numbers,
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
    parametrize_target_entities("number"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "power.crossed_threshold",
            device_class=NumberDeviceClass.POWER,
            threshold_unit=UnitOfPower.WATT,
            unit_attributes=_POWER_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_power_trigger_number_crossed_threshold_behavior_first(
    hass: HomeAssistant,
    target_numbers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test power crossed_threshold trigger fires on the first number state change."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_numbers,
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
    parametrize_target_entities("number"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "power.crossed_threshold",
            device_class=NumberDeviceClass.POWER,
            threshold_unit=UnitOfPower.WATT,
            unit_attributes=_POWER_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_power_trigger_number_crossed_threshold_behavior_last(
    hass: HomeAssistant,
    target_numbers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test power crossed_threshold trigger fires when the last number changes state."""
    await assert_trigger_behavior_last(
        hass,
        target_entities=target_numbers,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )
