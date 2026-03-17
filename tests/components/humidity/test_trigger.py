"""Test humidity trigger."""

from typing import Any

import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY as CLIMATE_ATTR_CURRENT_HUMIDITY,
    HVACMode,
)
from homeassistant.components.humidifier import (
    ATTR_CURRENT_HUMIDITY as HUMIDIFIER_ATTR_CURRENT_HUMIDITY,
)
from homeassistant.components.weather import ATTR_WEATHER_HUMIDITY
from homeassistant.const import ATTR_DEVICE_CLASS, CONF_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant, ServiceCall

from tests.components.common import (
    TriggerStateDescription,
    arm_trigger,
    assert_trigger_behavior_any,
    assert_trigger_gated_by_labs_flag,
    parametrize_numerical_attribute_changed_trigger_states,
    parametrize_numerical_attribute_crossed_threshold_trigger_states,
    parametrize_numerical_state_value_changed_trigger_states,
    parametrize_numerical_state_value_crossed_threshold_trigger_states,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture
async def target_sensors(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple sensor entities associated with different targets."""
    return await target_entities(hass, "sensor")


@pytest.fixture
async def target_climates(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple climate entities associated with different targets."""
    return await target_entities(hass, "climate")


@pytest.fixture
async def target_humidifiers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple humidifier entities associated with different targets."""
    return await target_entities(hass, "humidifier")


@pytest.fixture
async def target_weathers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple weather entities associated with different targets."""
    return await target_entities(hass, "weather")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "humidity.changed",
        "humidity.crossed_threshold",
    ],
)
async def test_humidity_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the humidity triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


# --- Sensor domain tests (value in state.state) ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_state_value_changed_trigger_states(
            "humidity.changed", "humidity"
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "humidity.crossed_threshold", "humidity"
        ),
    ],
)
async def test_humidity_trigger_sensor_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test humidity trigger fires for sensor entities with device_class humidity."""
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
            "humidity.crossed_threshold", "humidity"
        ),
    ],
)
async def test_humidity_trigger_sensor_crossed_threshold_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test humidity crossed_threshold trigger fires on the first sensor state change."""
    other_entity_ids = set(target_sensors["included"]) - {entity_id}

    for eid in target_sensors["included"]:
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

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "humidity.crossed_threshold", "humidity"
        ),
    ],
)
async def test_humidity_trigger_sensor_crossed_threshold_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test humidity crossed_threshold trigger fires when the last sensor changes state."""
    other_entity_ids = set(target_sensors["included"]) - {entity_id}

    for eid in target_sensors["included"]:
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


# --- Climate domain tests (value in current_humidity attribute) ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_changed_trigger_states(
            "humidity.changed", HVACMode.AUTO, CLIMATE_ATTR_CURRENT_HUMIDITY
        ),
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "humidity.crossed_threshold",
            HVACMode.AUTO,
            CLIMATE_ATTR_CURRENT_HUMIDITY,
        ),
    ],
)
async def test_humidity_trigger_climate_behavior_any(
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
    """Test humidity trigger fires for climate entities."""
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
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "humidity.crossed_threshold",
            HVACMode.AUTO,
            CLIMATE_ATTR_CURRENT_HUMIDITY,
        ),
    ],
)
async def test_humidity_trigger_climate_crossed_threshold_behavior_first(
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
    """Test humidity crossed_threshold trigger fires on the first climate state change."""
    other_entity_ids = set(target_climates["included"]) - {entity_id}

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
            "humidity.crossed_threshold",
            HVACMode.AUTO,
            CLIMATE_ATTR_CURRENT_HUMIDITY,
        ),
    ],
)
async def test_humidity_trigger_climate_crossed_threshold_behavior_last(
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
    """Test humidity crossed_threshold trigger fires when the last climate changes state."""
    other_entity_ids = set(target_climates["included"]) - {entity_id}

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


# --- Humidifier domain tests (value in current_humidity attribute) ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_changed_trigger_states(
            "humidity.changed", STATE_ON, HUMIDIFIER_ATTR_CURRENT_HUMIDITY
        ),
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "humidity.crossed_threshold",
            STATE_ON,
            HUMIDIFIER_ATTR_CURRENT_HUMIDITY,
        ),
    ],
)
async def test_humidity_trigger_humidifier_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_humidifiers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test humidity trigger fires for humidifier entities."""
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
        target_entities=target_humidifiers,
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
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "humidity.crossed_threshold",
            STATE_ON,
            HUMIDIFIER_ATTR_CURRENT_HUMIDITY,
        ),
    ],
)
async def test_humidity_trigger_humidifier_crossed_threshold_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_humidifiers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test humidity crossed_threshold trigger fires on the first humidifier state change."""
    other_entity_ids = set(target_humidifiers["included"]) - {entity_id}

    for eid in target_humidifiers["included"]:
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

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "humidity.crossed_threshold",
            STATE_ON,
            HUMIDIFIER_ATTR_CURRENT_HUMIDITY,
        ),
    ],
)
async def test_humidity_trigger_humidifier_crossed_threshold_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_humidifiers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test humidity crossed_threshold trigger fires when the last humidifier changes state."""
    other_entity_ids = set(target_humidifiers["included"]) - {entity_id}

    for eid in target_humidifiers["included"]:
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


# --- Weather domain tests (value in humidity attribute) ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("weather"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_changed_trigger_states(
            "humidity.changed", "sunny", ATTR_WEATHER_HUMIDITY
        ),
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "humidity.crossed_threshold",
            "sunny",
            ATTR_WEATHER_HUMIDITY,
        ),
    ],
)
async def test_humidity_trigger_weather_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_weathers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test humidity trigger fires for weather entities."""
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
        target_entities=target_weathers,
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
    parametrize_target_entities("weather"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "humidity.crossed_threshold",
            "sunny",
            ATTR_WEATHER_HUMIDITY,
        ),
    ],
)
async def test_humidity_trigger_weather_crossed_threshold_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_weathers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test humidity crossed_threshold trigger fires on the first weather state change."""
    other_entity_ids = set(target_weathers["included"]) - {entity_id}

    for eid in target_weathers["included"]:
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

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("weather"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "humidity.crossed_threshold",
            "sunny",
            ATTR_WEATHER_HUMIDITY,
        ),
    ],
)
async def test_humidity_trigger_weather_crossed_threshold_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_weathers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test humidity crossed_threshold trigger fires when the last weather changes state."""
    other_entity_ids = set(target_weathers["included"]) - {entity_id}

    for eid in target_weathers["included"]:
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


# --- Device class exclusion test ---


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
            "humidity.changed",
            {},
            "50",
            "60",
        ),
        (
            "humidity.crossed_threshold",
            {"threshold_type": "above", "lower_limit": 10},
            "5",
            "50",
        ),
    ],
)
async def test_humidity_trigger_excludes_non_humidity_sensor(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    trigger_key: str,
    trigger_options: dict[str, Any],
    sensor_initial: str,
    sensor_target: str,
) -> None:
    """Test humidity trigger does not fire for sensor entities without device_class humidity."""
    entity_id_humidity = "sensor.test_humidity"
    entity_id_temperature = "sensor.test_temperature"

    # Set initial states
    hass.states.async_set(
        entity_id_humidity, sensor_initial, {ATTR_DEVICE_CLASS: "humidity"}
    )
    hass.states.async_set(
        entity_id_temperature, sensor_initial, {ATTR_DEVICE_CLASS: "temperature"}
    )
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        trigger_key,
        trigger_options,
        {
            CONF_ENTITY_ID: [
                entity_id_humidity,
                entity_id_temperature,
            ]
        },
    )

    # Humidity sensor changes - should trigger
    hass.states.async_set(
        entity_id_humidity, sensor_target, {ATTR_DEVICE_CLASS: "humidity"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id_humidity
    service_calls.clear()

    # Temperature sensor changes - should NOT trigger (wrong device class)
    hass.states.async_set(
        entity_id_temperature, sensor_target, {ATTR_DEVICE_CLASS: "temperature"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0
