"""Test battery triggers."""

from typing import Any

import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, ServiceCall

from tests.components.common import (
    TriggerStateDescription,
    arm_trigger,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_behavior_last,
    assert_trigger_gated_by_labs_flag,
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


@pytest.fixture
async def target_numbers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple number entities associated with different targets."""
    return await target_entities(hass, "number")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "battery.low",
        "battery.not_low",
        "battery.started_charging",
        "battery.stopped_charging",
        "battery.percentage_changed",
        "battery.percentage_crossed_threshold",
    ],
)
async def test_battery_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the battery triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


# --- low / high (binary_sensor with device_class battery) ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="battery.low",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery"},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="battery.not_low",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery"},
            trigger_from_none=False,
        ),
    ],
)
async def test_battery_low_high_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test the battery low/high triggers with 'any' behavior."""
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
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
            trigger="battery.low",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery"},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="battery.not_low",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery"},
            trigger_from_none=False,
        ),
    ],
)
async def test_battery_low_high_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test the battery low/high triggers with 'first' behavior."""
    await assert_trigger_behavior_first(
        hass,
        service_calls=service_calls,
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
            trigger="battery.low",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery"},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="battery.not_low",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery"},
            trigger_from_none=False,
        ),
    ],
)
async def test_battery_low_high_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test the battery low/high triggers with 'last' behavior."""
    await assert_trigger_behavior_last(
        hass,
        service_calls=service_calls,
        target_entities=target_binary_sensors,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


# --- started_charging / stopped_charging (binary_sensor with device_class battery_charging) ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="battery.started_charging",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery_charging"},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="battery.stopped_charging",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery_charging"},
            trigger_from_none=False,
        ),
    ],
)
async def test_battery_charging_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test the battery started_charging/stopped_charging triggers with 'any' behavior."""
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
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
            trigger="battery.started_charging",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery_charging"},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="battery.stopped_charging",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery_charging"},
            trigger_from_none=False,
        ),
    ],
)
async def test_battery_charging_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test the battery started_charging/stopped_charging triggers with 'first' behavior."""
    await assert_trigger_behavior_first(
        hass,
        service_calls=service_calls,
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
            trigger="battery.started_charging",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery_charging"},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="battery.stopped_charging",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery_charging"},
            trigger_from_none=False,
        ),
    ],
)
async def test_battery_charging_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test the battery started_charging/stopped_charging triggers with 'last' behavior."""
    await assert_trigger_behavior_last(
        hass,
        service_calls=service_calls,
        target_entities=target_binary_sensors,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


# --- Device class exclusion for low/high ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    (
        "trigger_key",
        "trigger_options",
        "initial_state",
        "target_state",
        "device_class",
    ),
    [
        ("battery.low", {}, STATE_OFF, STATE_ON, "battery"),
        ("battery.not_low", {}, STATE_ON, STATE_OFF, "battery"),
        ("battery.started_charging", {}, STATE_OFF, STATE_ON, "battery_charging"),
        ("battery.stopped_charging", {}, STATE_ON, STATE_OFF, "battery_charging"),
    ],
)
async def test_battery_trigger_excludes_wrong_device_class(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    trigger_key: str,
    trigger_options: dict[str, Any],
    initial_state: str,
    target_state: str,
    device_class: str,
) -> None:
    """Test battery triggers do not fire for entities with wrong device class."""
    entity_correct = "binary_sensor.test_correct"
    entity_wrong = "binary_sensor.test_wrong"

    # Set initial states
    hass.states.async_set(
        entity_correct, initial_state, {ATTR_DEVICE_CLASS: device_class}
    )
    hass.states.async_set(entity_wrong, initial_state, {ATTR_DEVICE_CLASS: "door"})
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        trigger_key,
        trigger_options,
        {CONF_ENTITY_ID: [entity_correct, entity_wrong]},
    )

    # Wrong device class changes to target state - should NOT trigger
    hass.states.async_set(entity_wrong, target_state, {ATTR_DEVICE_CLASS: "door"})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Correct device class changes to target state - should trigger
    hass.states.async_set(
        entity_correct, target_state, {ATTR_DEVICE_CLASS: device_class}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_correct


# --- percentage_changed (sensor with device_class battery) ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_state_value_changed_trigger_states(
            "battery.percentage_changed",
            device_class=SensorDeviceClass.BATTERY,
            unit_attributes={ATTR_UNIT_OF_MEASUREMENT: "%"},
        ),
    ],
)
async def test_battery_percentage_changed_sensor_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_sensors: dict[str, list[str]],
    trigger_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test battery percentage_changed trigger fires for sensor entities."""
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
        target_entities=target_sensors,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


# --- percentage_crossed_threshold (sensor with device_class battery) ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "battery.percentage_crossed_threshold",
            device_class=SensorDeviceClass.BATTERY,
            unit_attributes={ATTR_UNIT_OF_MEASUREMENT: "%"},
        ),
    ],
)
async def test_battery_percentage_crossed_threshold_sensor_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_sensors: dict[str, list[str]],
    trigger_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test battery percentage_crossed_threshold trigger fires for sensor entities."""
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
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
            "battery.percentage_crossed_threshold",
            device_class=SensorDeviceClass.BATTERY,
            unit_attributes={ATTR_UNIT_OF_MEASUREMENT: "%"},
        ),
    ],
)
async def test_battery_percentage_crossed_threshold_sensor_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_sensors: dict[str, list[str]],
    trigger_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test battery percentage_crossed_threshold trigger fires on the first sensor state change."""
    await assert_trigger_behavior_first(
        hass,
        service_calls=service_calls,
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
            "battery.percentage_crossed_threshold",
            device_class=SensorDeviceClass.BATTERY,
            unit_attributes={ATTR_UNIT_OF_MEASUREMENT: "%"},
        ),
    ],
)
async def test_battery_percentage_crossed_threshold_sensor_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_sensors: dict[str, list[str]],
    trigger_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test battery percentage_crossed_threshold trigger fires when the last sensor changes state."""
    await assert_trigger_behavior_last(
        hass,
        service_calls=service_calls,
        target_entities=target_sensors,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


# --- Device class exclusion for percentage triggers ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    (
        "trigger_key",
        "trigger_options",
        "sensor_initial",
        "sensor_target",
    ),
    [
        (
            "battery.percentage_changed",
            {},
            "50",
            "60",
        ),
        (
            "battery.percentage_crossed_threshold",
            {"threshold_type": "above", "lower_limit": 10},
            "5",
            "50",
        ),
    ],
)
async def test_battery_percentage_trigger_excludes_non_battery_sensor(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    trigger_key: str,
    trigger_options: dict[str, Any],
    sensor_initial: str,
    sensor_target: str,
) -> None:
    """Test battery percentage trigger does not fire for sensor entities without device_class battery."""
    entity_id_battery = "sensor.test_battery"
    entity_id_temperature = "sensor.test_temperature"

    # Set initial states
    battery_attrs = {ATTR_DEVICE_CLASS: "battery", ATTR_UNIT_OF_MEASUREMENT: "%"}
    temperature_attrs = {
        ATTR_DEVICE_CLASS: "temperature",
        ATTR_UNIT_OF_MEASUREMENT: "°C",
    }

    hass.states.async_set(entity_id_battery, sensor_initial, battery_attrs)
    hass.states.async_set(entity_id_temperature, sensor_initial, temperature_attrs)
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        trigger_key,
        trigger_options,
        {
            CONF_ENTITY_ID: [
                entity_id_battery,
                entity_id_temperature,
            ]
        },
    )

    # Battery sensor changes - should trigger
    hass.states.async_set(entity_id_battery, sensor_target, battery_attrs)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id_battery
    service_calls.clear()

    # Temperature sensor changes - should NOT trigger (wrong device class)
    hass.states.async_set(entity_id_temperature, sensor_target, temperature_attrs)
    await hass.async_block_till_done()
    assert len(service_calls) == 0
