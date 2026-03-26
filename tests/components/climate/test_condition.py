"""Test climate conditions."""

from typing import Any

import pytest

from homeassistant.components.climate.const import (
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    assert_numerical_condition_unit_conversion,
    other_states,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_numerical_attribute_condition_above_below_all,
    parametrize_numerical_attribute_condition_above_below_any,
    parametrize_target_entities,
    target_entities,
)


@pytest.fixture
async def target_climates(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple climate entities associated with different targets."""
    return await target_entities(hass, "climate")


@pytest.mark.parametrize(
    "condition",
    [
        "climate.is_off",
        "climate.is_on",
        "climate.is_cooling",
        "climate.is_drying",
        "climate.is_heating",
        "climate.target_humidity",
        "climate.target_temperature",
    ],
)
async def test_climate_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the climate conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="climate.is_off",
            target_states=[HVACMode.OFF],
            other_states=other_states(HVACMode.OFF),
        ),
        *parametrize_condition_states_any(
            condition="climate.is_on",
            target_states=[
                HVACMode.AUTO,
                HVACMode.COOL,
                HVACMode.DRY,
                HVACMode.FAN_ONLY,
                HVACMode.HEAT,
                HVACMode.HEAT_COOL,
            ],
            other_states=[HVACMode.OFF],
        ),
    ],
)
async def test_climate_state_condition_behavior_any(
    hass: HomeAssistant,
    target_climates: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the climate state condition with the 'any' behavior."""
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
    [
        *parametrize_condition_states_all(
            condition="climate.is_off",
            target_states=[HVACMode.OFF],
            other_states=other_states(HVACMode.OFF),
        ),
        *parametrize_condition_states_all(
            condition="climate.is_on",
            target_states=[
                HVACMode.AUTO,
                HVACMode.COOL,
                HVACMode.DRY,
                HVACMode.FAN_ONLY,
                HVACMode.HEAT,
                HVACMode.HEAT_COOL,
            ],
            other_states=[HVACMode.OFF],
        ),
    ],
)
async def test_climate_state_condition_behavior_all(
    hass: HomeAssistant,
    target_climates: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the climate state condition with the 'all' behavior."""
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
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="climate.is_cooling",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.COOLING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
        *parametrize_condition_states_any(
            condition="climate.is_drying",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.DRYING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
        *parametrize_condition_states_any(
            condition="climate.is_heating",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.HEATING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
    ],
)
async def test_climate_attribute_condition_behavior_any(
    hass: HomeAssistant,
    target_climates: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the climate attribute condition with the 'any' behavior."""
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
    [
        *parametrize_condition_states_all(
            condition="climate.is_cooling",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.COOLING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
        *parametrize_condition_states_all(
            condition="climate.is_drying",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.DRYING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
        *parametrize_condition_states_all(
            condition="climate.is_heating",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.HEATING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
    ],
)
async def test_climate_attribute_condition_behavior_all(
    hass: HomeAssistant,
    target_climates: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the climate attribute condition with the 'all' behavior."""
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
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_numerical_attribute_condition_above_below_any(
            "climate.target_humidity",
            HVACMode.AUTO,
            ATTR_HUMIDITY,
        ),
        *parametrize_numerical_attribute_condition_above_below_any(
            "climate.target_temperature",
            HVACMode.AUTO,
            ATTR_TEMPERATURE,
            threshold_unit=UnitOfTemperature.CELSIUS,
        ),
    ],
)
async def test_climate_numerical_condition_behavior_any(
    hass: HomeAssistant,
    target_climates: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the climate numerical condition with the 'any' behavior."""
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
    [
        *parametrize_numerical_attribute_condition_above_below_all(
            "climate.target_humidity",
            HVACMode.AUTO,
            ATTR_HUMIDITY,
        ),
        *parametrize_numerical_attribute_condition_above_below_all(
            "climate.target_temperature",
            HVACMode.AUTO,
            ATTR_TEMPERATURE,
            threshold_unit=UnitOfTemperature.CELSIUS,
        ),
    ],
)
async def test_climate_numerical_condition_behavior_all(
    hass: HomeAssistant,
    target_climates: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the climate numerical condition with the 'all' behavior."""
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
async def test_climate_numerical_condition_unit_conversion(hass: HomeAssistant) -> None:
    """Test that the climate numerical condition converts units correctly."""
    _unit_celsius = {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    _unit_fahrenheit = {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT}
    _unit_invalid = {ATTR_UNIT_OF_MEASUREMENT: "not_a_valid_unit"}

    await assert_numerical_condition_unit_conversion(
        hass,
        condition="climate.target_temperature",
        entity_id="climate.test",
        pass_states=[{"state": HVACMode.AUTO, "attributes": {ATTR_TEMPERATURE: 25}}],
        fail_states=[
            {
                "state": HVACMode.AUTO,
                "attributes": {ATTR_TEMPERATURE: 20},
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
