"""Test temperature conditions."""

from typing import Any

import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.weather import ATTR_WEATHER_TEMPERATURE_UNIT
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfTemperature
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    assert_numerical_condition_unit_conversion,
    parametrize_numerical_attribute_condition_above_below_all,
    parametrize_numerical_attribute_condition_above_below_any,
    parametrize_numerical_condition_above_below_all,
    parametrize_numerical_condition_above_below_any,
    parametrize_target_entities,
    target_entities,
)

_WEATHER_UNIT_ATTRIBUTES = {ATTR_WEATHER_TEMPERATURE_UNIT: UnitOfTemperature.CELSIUS}


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
    """Create multiple water heater entities associated with different targets."""
    return await target_entities(hass, "water_heater")


@pytest.fixture
async def target_weathers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple weather entities associated with different targets."""
    return await target_entities(hass, "weather")


@pytest.mark.parametrize(
    "condition",
    ["temperature.is_value"],
)
async def test_temperature_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the temperature conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("sensor"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_numerical_condition_above_below_any(
        "temperature.is_value",
        device_class="temperature",
        threshold_unit=UnitOfTemperature.CELSIUS,
        unit_attributes={ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    ),
)
async def test_temperature_sensor_condition_behavior_any(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the temperature sensor condition with 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_sensors,
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
    parametrize_target_entities("sensor"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_numerical_condition_above_below_all(
        "temperature.is_value",
        device_class="temperature",
        threshold_unit=UnitOfTemperature.CELSIUS,
        unit_attributes={ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    ),
)
async def test_temperature_sensor_condition_behavior_all(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the temperature sensor condition with 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_sensors,
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
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_numerical_attribute_condition_above_below_any(
        "temperature.is_value",
        HVACMode.AUTO,
        "current_temperature",
        threshold_unit=UnitOfTemperature.CELSIUS,
    ),
)
async def test_temperature_climate_condition_behavior_any(
    hass: HomeAssistant,
    target_climates: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the temperature climate condition with 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_climates,
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
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_numerical_attribute_condition_above_below_all(
        "temperature.is_value",
        HVACMode.AUTO,
        "current_temperature",
        threshold_unit=UnitOfTemperature.CELSIUS,
    ),
)
async def test_temperature_climate_condition_behavior_all(
    hass: HomeAssistant,
    target_climates: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the temperature climate condition with 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_climates,
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
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_numerical_attribute_condition_above_below_any(
        "temperature.is_value",
        "eco",
        "current_temperature",
        threshold_unit=UnitOfTemperature.CELSIUS,
    ),
)
async def test_temperature_water_heater_condition_behavior_any(
    hass: HomeAssistant,
    target_water_heaters: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the temperature water heater condition with 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_water_heaters,
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
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_numerical_attribute_condition_above_below_all(
        "temperature.is_value",
        "eco",
        "current_temperature",
        threshold_unit=UnitOfTemperature.CELSIUS,
    ),
)
async def test_temperature_water_heater_condition_behavior_all(
    hass: HomeAssistant,
    target_water_heaters: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the temperature water heater condition with 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_water_heaters,
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
    parametrize_target_entities("weather"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_numerical_attribute_condition_above_below_any(
        "temperature.is_value",
        "sunny",
        "temperature",
        threshold_unit=UnitOfTemperature.CELSIUS,
        unit_attributes=_WEATHER_UNIT_ATTRIBUTES,
    ),
)
async def test_temperature_weather_condition_behavior_any(
    hass: HomeAssistant,
    target_weathers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the temperature weather condition with 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_weathers,
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
    parametrize_target_entities("weather"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_numerical_attribute_condition_above_below_all(
        "temperature.is_value",
        "sunny",
        "temperature",
        threshold_unit=UnitOfTemperature.CELSIUS,
        unit_attributes=_WEATHER_UNIT_ATTRIBUTES,
    ),
)
async def test_temperature_weather_condition_behavior_all(
    hass: HomeAssistant,
    target_weathers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the temperature weather condition with 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_weathers,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_temperature_condition_unit_conversion_sensor(
    hass: HomeAssistant,
) -> None:
    """Test that the temperature condition converts units correctly for sensors."""
    _unit_celsius = {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    _unit_fahrenheit = {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT}
    _unit_invalid = {ATTR_UNIT_OF_MEASUREMENT: "not_a_valid_unit"}

    await assert_numerical_condition_unit_conversion(
        hass,
        condition="temperature.is_value",
        entity_id="sensor.test",
        pass_states=[
            {
                "state": "25",
                "attributes": {
                    "device_class": "temperature",
                    ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
                },
            }
        ],
        fail_states=[
            {
                "state": "20",
                "attributes": {
                    "device_class": "temperature",
                    ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
                },
            }
        ],
        numerical_condition_options=[
            {
                "threshold": {
                    "type": "between",
                    "value_min": {
                        "number": 75,
                        "unit_of_measurement": UnitOfTemperature.FAHRENHEIT,
                    },
                    "value_max": {
                        "number": 90,
                        "unit_of_measurement": UnitOfTemperature.FAHRENHEIT,
                    },
                }
            },
            {
                "threshold": {
                    "type": "between",
                    "value_min": {
                        "number": 24,
                        "unit_of_measurement": UnitOfTemperature.CELSIUS,
                    },
                    "value_max": {
                        "number": 30,
                        "unit_of_measurement": UnitOfTemperature.CELSIUS,
                    },
                }
            },
        ],
        limit_entity_condition_options={
            "threshold": {
                "type": "between",
                "value_min": {"entity": "sensor.above"},
                "value_max": {"entity": "sensor.below"},
            }
        },
        limit_entities=("sensor.above", "sensor.below"),
        limit_entity_states=[
            (
                {"state": "75", "attributes": _unit_fahrenheit},  # ≈23.9°C
                {"state": "90", "attributes": _unit_fahrenheit},  # ≈32.2°C
            ),
            (
                {"state": "24", "attributes": _unit_celsius},
                {"state": "30", "attributes": _unit_celsius},
            ),
        ],
        invalid_limit_entity_states=[
            (
                {"state": "75", "attributes": _unit_invalid},
                {"state": "90", "attributes": _unit_invalid},
            ),
            (
                {"state": "24", "attributes": _unit_invalid},
                {"state": "30", "attributes": _unit_invalid},
            ),
        ],
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_temperature_condition_unit_conversion_climate(
    hass: HomeAssistant,
) -> None:
    """Test that the temperature condition converts units correctly for climate."""
    _unit_celsius = {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    _unit_fahrenheit = {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT}
    _unit_invalid = {ATTR_UNIT_OF_MEASUREMENT: "not_a_valid_unit"}

    await assert_numerical_condition_unit_conversion(
        hass,
        condition="temperature.is_value",
        entity_id="climate.test",
        pass_states=[
            {"state": HVACMode.AUTO, "attributes": {"current_temperature": 25}}
        ],
        fail_states=[
            {"state": HVACMode.AUTO, "attributes": {"current_temperature": 20}}
        ],
        numerical_condition_options=[
            {
                "threshold": {
                    "type": "between",
                    "value_min": {
                        "number": 75,
                        "unit_of_measurement": UnitOfTemperature.FAHRENHEIT,
                    },
                    "value_max": {
                        "number": 90,
                        "unit_of_measurement": UnitOfTemperature.FAHRENHEIT,
                    },
                }
            },
            {
                "threshold": {
                    "type": "between",
                    "value_min": {
                        "number": 24,
                        "unit_of_measurement": UnitOfTemperature.CELSIUS,
                    },
                    "value_max": {
                        "number": 30,
                        "unit_of_measurement": UnitOfTemperature.CELSIUS,
                    },
                }
            },
        ],
        limit_entity_condition_options={
            "threshold": {
                "type": "between",
                "value_min": {"entity": "sensor.above"},
                "value_max": {"entity": "sensor.below"},
            }
        },
        limit_entities=("sensor.above", "sensor.below"),
        limit_entity_states=[
            (
                {"state": "75", "attributes": _unit_fahrenheit},
                {"state": "90", "attributes": _unit_fahrenheit},
            ),
            (
                {"state": "24", "attributes": _unit_celsius},
                {"state": "30", "attributes": _unit_celsius},
            ),
        ],
        invalid_limit_entity_states=[
            (
                {"state": "75", "attributes": _unit_invalid},
                {"state": "90", "attributes": _unit_invalid},
            ),
            (
                {"state": "24", "attributes": _unit_invalid},
                {"state": "30", "attributes": _unit_invalid},
            ),
        ],
    )
