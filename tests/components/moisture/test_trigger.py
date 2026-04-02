"""Test moisture trigger."""

from typing import Any

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from tests.components.common import (
    TriggerStateDescription,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_behavior_last,
    assert_trigger_gated_by_labs_flag,
    assert_trigger_ignores_limit_entities_with_wrong_unit,
    parametrize_numerical_state_value_changed_trigger_states,
    parametrize_numerical_state_value_crossed_threshold_trigger_states,
    parametrize_target_entities,
    parametrize_trigger_states,
    target_entities,
)


@pytest.fixture
async def target_binary_sensors(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple binary sensor entities associated with different targets."""
    return await target_entities(hass, "binary_sensor")


@pytest.fixture
async def target_sensors(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple sensor entities associated with different targets."""
    return await target_entities(hass, "sensor")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "moisture.detected",
        "moisture.cleared",
        "moisture.changed",
        "moisture.crossed_threshold",
    ],
)
async def test_moisture_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the moisture triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="moisture.detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOISTURE
            },
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="moisture.cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOISTURE
            },
            trigger_from_none=False,
        ),
    ],
)
async def test_moisture_trigger_binary_sensor_behavior_any(
    hass: HomeAssistant,
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test moisture trigger fires for binary_sensor entities with device_class moisture."""
    await assert_trigger_behavior_any(
        hass,
        target_entities=target_binary_sensors,
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
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="moisture.detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOISTURE
            },
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="moisture.cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOISTURE
            },
            trigger_from_none=False,
        ),
    ],
)
async def test_moisture_trigger_binary_sensor_behavior_first(
    hass: HomeAssistant,
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test moisture trigger fires on the first binary_sensor state change."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_binary_sensors,
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
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="moisture.detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOISTURE
            },
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="moisture.cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOISTURE
            },
            trigger_from_none=False,
        ),
    ],
)
async def test_moisture_trigger_binary_sensor_behavior_last(
    hass: HomeAssistant,
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test moisture trigger fires when the last binary_sensor changes state."""
    await assert_trigger_behavior_last(
        hass,
        target_entities=target_binary_sensors,
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
        *parametrize_numerical_state_value_changed_trigger_states(
            "moisture.changed",
            device_class=SensorDeviceClass.MOISTURE,
            unit_attributes={ATTR_UNIT_OF_MEASUREMENT: "%"},
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "moisture.crossed_threshold",
            device_class=SensorDeviceClass.MOISTURE,
            unit_attributes={ATTR_UNIT_OF_MEASUREMENT: "%"},
        ),
    ],
)
async def test_moisture_trigger_sensor_behavior_any(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test moisture trigger fires for sensor entities with device_class moisture."""
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
            "moisture.crossed_threshold",
            device_class=SensorDeviceClass.MOISTURE,
            unit_attributes={ATTR_UNIT_OF_MEASUREMENT: "%"},
        ),
    ],
)
async def test_moisture_trigger_sensor_crossed_threshold_behavior_first(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test moisture crossed_threshold trigger fires on the first sensor state change."""
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
            "moisture.crossed_threshold",
            device_class=SensorDeviceClass.MOISTURE,
            unit_attributes={ATTR_UNIT_OF_MEASUREMENT: "%"},
        ),
    ],
)
async def test_moisture_trigger_sensor_crossed_threshold_behavior_last(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test moisture crossed_threshold trigger fires when the last sensor changes state."""
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


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "limit_entities"),
    [
        (
            "moisture.changed",
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"entity": "sensor.moisture_above"},
                    "value_max": {"entity": "sensor.moisture_below"},
                },
            },
            ["sensor.moisture_above", "sensor.moisture_below"],
        ),
        (
            "moisture.crossed_threshold",
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"entity": "sensor.moisture_lower"},
                    "value_max": {"entity": "sensor.moisture_upper"},
                },
            },
            ["sensor.moisture_lower", "sensor.moisture_upper"],
        ),
    ],
)
async def test_moisture_trigger_ignores_limit_entity_with_wrong_unit(
    hass: HomeAssistant,
    trigger: str,
    trigger_options: dict[str, Any],
    limit_entities: list[str],
) -> None:
    """Test numerical triggers do not fire if limit entities have the wrong unit."""
    moisture_attrs = {
        ATTR_DEVICE_CLASS: SensorDeviceClass.MOISTURE,
        ATTR_UNIT_OF_MEASUREMENT: "%",
    }
    await assert_trigger_ignores_limit_entities_with_wrong_unit(
        hass,
        trigger=trigger,
        trigger_options=trigger_options,
        entity_id="sensor.test_moisture",
        reset_state={"state": "0", "attributes": moisture_attrs},
        trigger_state={"state": "50", "attributes": moisture_attrs},
        limit_entities=[
            (limit_entities[0], "10"),
            (limit_entities[1], "90"),
        ],
        correct_unit="%",
        wrong_unit="g/m³",
    )
