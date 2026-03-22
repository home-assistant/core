"""Test temperature trigger."""

from typing import Any

import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE as CLIMATE_ATTR_CURRENT_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.water_heater import (
    ATTR_CURRENT_TEMPERATURE as WATER_HEATER_ATTR_CURRENT_TEMPERATURE,
)
from homeassistant.components.weather import (
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_TEMPERATURE_UNIT,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_ID,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, ServiceCall

from tests.components.common import (
    TriggerStateDescription,
    arm_trigger,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_behavior_last,
    assert_trigger_gated_by_labs_flag,
    parametrize_numerical_attribute_changed_trigger_states,
    parametrize_numerical_attribute_crossed_threshold_trigger_states,
    parametrize_numerical_state_value_changed_trigger_states,
    parametrize_numerical_state_value_crossed_threshold_trigger_states,
    parametrize_target_entities,
    target_entities,
)

_TEMPERATURE_TRIGGER_OPTIONS = {"unit": UnitOfTemperature.CELSIUS}
_SENSOR_UNIT_ATTRIBUTES = {
    ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
}
_WEATHER_UNIT_ATTRIBUTES = {
    ATTR_WEATHER_TEMPERATURE_UNIT: UnitOfTemperature.CELSIUS,
}


@pytest.fixture
async def target_sensors(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple sensor entities associated with different targets."""
    return await target_entities(hass, "sensor")


@pytest.fixture
async def target_climates(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple climate entities associated with different targets."""
    return await target_entities(hass, "climate")


@pytest.fixture
async def target_water_heaters(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple water_heater entities associated with different targets."""
    return await target_entities(hass, "water_heater")


@pytest.fixture
async def target_weathers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple weather entities associated with different targets."""
    return await target_entities(hass, "weather")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "temperature.changed",
        "temperature.crossed_threshold",
    ],
)
async def test_temperature_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the temperature triggers are gated by the labs flag."""
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
            "temperature.changed",
            device_class=SensorDeviceClass.TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
            unit_attributes=_SENSOR_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "temperature.crossed_threshold",
            device_class=SensorDeviceClass.TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
            unit_attributes=_SENSOR_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_temperature_trigger_sensor_behavior_any(
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
    """Test temperature trigger fires for sensor entities with device_class temperature."""
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
            "temperature.crossed_threshold",
            device_class=SensorDeviceClass.TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
            unit_attributes=_SENSOR_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_temperature_trigger_sensor_crossed_threshold_behavior_first(
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
    """Test temperature crossed_threshold trigger fires on the first sensor state change."""
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
            "temperature.crossed_threshold",
            device_class=SensorDeviceClass.TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
            unit_attributes=_SENSOR_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_temperature_trigger_sensor_crossed_threshold_behavior_last(
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
    """Test temperature crossed_threshold trigger fires when the last sensor changes state."""
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


# --- Climate domain tests (value in current_temperature attribute) ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_changed_trigger_states(
            "temperature.changed",
            HVACMode.AUTO,
            CLIMATE_ATTR_CURRENT_TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
        ),
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "temperature.crossed_threshold",
            HVACMode.AUTO,
            CLIMATE_ATTR_CURRENT_TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
        ),
    ],
)
async def test_temperature_trigger_climate_behavior_any(
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
    """Test temperature trigger fires for climate entities."""
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
            "temperature.crossed_threshold",
            HVACMode.AUTO,
            CLIMATE_ATTR_CURRENT_TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
        ),
    ],
)
async def test_temperature_trigger_climate_crossed_threshold_behavior_first(
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
    """Test temperature crossed_threshold trigger fires on the first climate state change."""
    await assert_trigger_behavior_first(
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
            "temperature.crossed_threshold",
            HVACMode.AUTO,
            CLIMATE_ATTR_CURRENT_TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
        ),
    ],
)
async def test_temperature_trigger_climate_crossed_threshold_behavior_last(
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
    """Test temperature crossed_threshold trigger fires when the last climate changes state."""
    await assert_trigger_behavior_last(
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


# --- Water heater domain tests (value in current_temperature attribute) ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_changed_trigger_states(
            "temperature.changed",
            "eco",
            WATER_HEATER_ATTR_CURRENT_TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
        ),
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "temperature.crossed_threshold",
            "eco",
            WATER_HEATER_ATTR_CURRENT_TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
        ),
    ],
)
async def test_temperature_trigger_water_heater_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_water_heaters: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test temperature trigger fires for water_heater entities."""
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
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "temperature.crossed_threshold",
            "eco",
            WATER_HEATER_ATTR_CURRENT_TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
        ),
    ],
)
async def test_temperature_trigger_water_heater_crossed_threshold_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_water_heaters: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test temperature crossed_threshold trigger fires on the first water_heater state change."""
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
            "temperature.crossed_threshold",
            "eco",
            WATER_HEATER_ATTR_CURRENT_TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
        ),
    ],
)
async def test_temperature_trigger_water_heater_crossed_threshold_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_water_heaters: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test temperature crossed_threshold trigger fires when the last water_heater changes state."""
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


# --- Weather domain tests (value in temperature attribute) ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("weather"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_changed_trigger_states(
            "temperature.changed",
            "sunny",
            ATTR_WEATHER_TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
            unit_attributes=_WEATHER_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "temperature.crossed_threshold",
            "sunny",
            ATTR_WEATHER_TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
            unit_attributes=_WEATHER_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_temperature_trigger_weather_behavior_any(
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
    """Test temperature trigger fires for weather entities."""
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
            "temperature.crossed_threshold",
            "sunny",
            ATTR_WEATHER_TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
            unit_attributes=_WEATHER_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_temperature_trigger_weather_crossed_threshold_behavior_first(
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
    """Test temperature crossed_threshold trigger fires on the first weather state change."""
    await assert_trigger_behavior_first(
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
            "temperature.crossed_threshold",
            "sunny",
            ATTR_WEATHER_TEMPERATURE,
            trigger_options=_TEMPERATURE_TRIGGER_OPTIONS,
            unit_attributes=_WEATHER_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_temperature_trigger_weather_crossed_threshold_behavior_last(
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
    """Test temperature crossed_threshold trigger fires when the last weather changes state."""
    await assert_trigger_behavior_last(
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
            "temperature.changed",
            {},
            "20",
            "25",
        ),
        (
            "temperature.crossed_threshold",
            {"threshold_type": "above", "lower_limit": 10, "unit": "°C"},
            "5",
            "20",
        ),
    ],
)
async def test_temperature_trigger_excludes_non_temperature_sensor(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    trigger_key: str,
    trigger_options: dict[str, Any],
    sensor_initial: str,
    sensor_target: str,
) -> None:
    """Test temperature trigger does not fire for sensor entities without device_class temperature."""
    entity_id_temperature = "sensor.test_temperature"
    entity_id_humidity = "sensor.test_humidity"

    temp_attrs = {
        ATTR_DEVICE_CLASS: "temperature",
        ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
    }
    humidity_attrs = {ATTR_DEVICE_CLASS: "humidity"}

    # Set initial states
    hass.states.async_set(entity_id_temperature, sensor_initial, temp_attrs)
    hass.states.async_set(entity_id_humidity, sensor_initial, humidity_attrs)
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        trigger_key,
        trigger_options,
        {
            CONF_ENTITY_ID: [
                entity_id_temperature,
                entity_id_humidity,
            ]
        },
    )

    # Temperature sensor changes - should trigger
    hass.states.async_set(entity_id_temperature, sensor_target, temp_attrs)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id_temperature
    service_calls.clear()

    # Humidity sensor changes - should NOT trigger (wrong device class)
    hass.states.async_set(entity_id_humidity, sensor_target, humidity_attrs)
    await hass.async_block_till_done()
    assert len(service_calls) == 0


# --- Unit conversion tests ---


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_temperature_trigger_unit_conversion_sensor_celsius_to_fahrenheit(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
) -> None:
    """Test temperature trigger converts sensor value from °C to °F for threshold comparison."""
    entity_id = "sensor.test_temp"

    # Sensor reports in °C, trigger configured in °F with threshold above 70°F
    hass.states.async_set(
        entity_id,
        "20",
        {
            ATTR_DEVICE_CLASS: "temperature",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        "temperature.crossed_threshold",
        {
            "threshold_type": "above",
            "lower_limit": 70,
            "unit": "°F",
        },
        {CONF_ENTITY_ID: [entity_id]},
    )

    # 20°C = 68°F, which is below 70°F - should NOT trigger
    hass.states.async_set(
        entity_id,
        "20",
        {
            ATTR_DEVICE_CLASS: "temperature",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # 22°C = 71.6°F, which is above 70°F - should trigger
    hass.states.async_set(
        entity_id,
        "22",
        {
            ATTR_DEVICE_CLASS: "temperature",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    service_calls.clear()


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_temperature_trigger_unit_conversion_sensor_fahrenheit_to_celsius(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
) -> None:
    """Test temperature trigger converts sensor value from °F to °C for threshold comparison."""
    entity_id = "sensor.test_temp"

    # Sensor reports in °F, trigger configured in °C with threshold above 25°C
    hass.states.async_set(
        entity_id,
        "70",
        {
            ATTR_DEVICE_CLASS: "temperature",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        },
    )
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        "temperature.crossed_threshold",
        {
            "threshold_type": "above",
            "lower_limit": 25,
            "unit": "°C",
        },
        {CONF_ENTITY_ID: [entity_id]},
    )

    # 70°F = 21.1°C, which is below 25°C - should NOT trigger
    hass.states.async_set(
        entity_id,
        "70",
        {
            ATTR_DEVICE_CLASS: "temperature",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # 80°F = 26.7°C, which is above 25°C - should trigger
    hass.states.async_set(
        entity_id,
        "80",
        {
            ATTR_DEVICE_CLASS: "temperature",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    service_calls.clear()


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_temperature_trigger_unit_conversion_changed(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
) -> None:
    """Test temperature changed trigger with unit conversion and above/below limits."""
    entity_id = "sensor.test_temp"

    # Sensor reports in °C, trigger configured in °F: above 68°F (20°C), below 77°F (25°C)
    hass.states.async_set(
        entity_id,
        "18",
        {
            ATTR_DEVICE_CLASS: "temperature",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        "temperature.changed",
        {
            "above": 68,
            "below": 77,
            "unit": "°F",
        },
        {CONF_ENTITY_ID: [entity_id]},
    )

    # 18°C = 64.4°F, below 68°F - should NOT trigger
    hass.states.async_set(
        entity_id,
        "19",
        {
            ATTR_DEVICE_CLASS: "temperature",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # 22°C = 71.6°F, between 68°F and 77°F - should trigger
    hass.states.async_set(
        entity_id,
        "22",
        {
            ATTR_DEVICE_CLASS: "temperature",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    service_calls.clear()

    # 26°C = 78.8°F, above 77°F - should NOT trigger
    hass.states.async_set(
        entity_id,
        "26",
        {
            ATTR_DEVICE_CLASS: "temperature",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_temperature_trigger_unit_conversion_weather(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
) -> None:
    """Test temperature trigger with unit conversion for weather entities."""
    entity_id = "weather.test"

    # Weather reports temperature in °F, trigger configured in °C with threshold above 25°C
    hass.states.async_set(
        entity_id,
        "sunny",
        {
            ATTR_WEATHER_TEMPERATURE: 70,
            ATTR_WEATHER_TEMPERATURE_UNIT: UnitOfTemperature.FAHRENHEIT,
        },
    )
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        "temperature.crossed_threshold",
        {
            "threshold_type": "above",
            "lower_limit": 25,
            "unit": "°C",
        },
        {CONF_ENTITY_ID: [entity_id]},
    )

    # 70°F = 21.1°C, below 25°C - should NOT trigger
    hass.states.async_set(
        entity_id,
        "sunny",
        {
            ATTR_WEATHER_TEMPERATURE: 70,
            ATTR_WEATHER_TEMPERATURE_UNIT: UnitOfTemperature.FAHRENHEIT,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # 80°F = 26.7°C, above 25°C - should trigger
    hass.states.async_set(
        entity_id,
        "sunny",
        {
            ATTR_WEATHER_TEMPERATURE: 80,
            ATTR_WEATHER_TEMPERATURE_UNIT: UnitOfTemperature.FAHRENHEIT,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    service_calls.clear()
