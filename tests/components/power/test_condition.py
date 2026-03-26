"""Test power conditions."""

from typing import Any

import pytest

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfPower
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    assert_numerical_condition_unit_conversion,
    parametrize_numerical_condition_above_below_all,
    parametrize_numerical_condition_above_below_any,
    parametrize_target_entities,
    target_entities,
)


@pytest.fixture
async def target_sensors(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple sensor entities associated with different targets."""
    return await target_entities(hass, "sensor")


@pytest.fixture
async def target_numbers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple number entities associated with different targets."""
    return await target_entities(hass, "number")


@pytest.mark.parametrize(
    "condition",
    ["power.is_value"],
)
async def test_power_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the power conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("sensor"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_numerical_condition_above_below_any(
        "power.is_value",
        device_class="power",
        threshold_unit=UnitOfPower.WATT,
        unit_attributes={ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    ),
)
async def test_power_sensor_condition_behavior_any(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the power sensor condition with 'any' behavior."""
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
        "power.is_value",
        device_class="power",
        threshold_unit=UnitOfPower.WATT,
        unit_attributes={ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    ),
)
async def test_power_sensor_condition_behavior_all(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the power sensor condition with 'all' behavior."""
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
    parametrize_target_entities("number"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_numerical_condition_above_below_any(
        "power.is_value",
        device_class="power",
        threshold_unit=UnitOfPower.WATT,
        unit_attributes={ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    ),
)
async def test_power_number_condition_behavior_any(
    hass: HomeAssistant,
    target_numbers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the power number condition with 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_numbers,
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
    parametrize_target_entities("number"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_numerical_condition_above_below_all(
        "power.is_value",
        device_class="power",
        threshold_unit=UnitOfPower.WATT,
        unit_attributes={ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT},
    ),
)
async def test_power_number_condition_behavior_all(
    hass: HomeAssistant,
    target_numbers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the power number condition with 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_numbers,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_power_condition_unit_conversion_sensor(
    hass: HomeAssistant,
) -> None:
    """Test that the power condition converts units correctly for sensors."""
    _unit_watt = {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT}
    _unit_kilowatt = {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT}
    _unit_invalid = {ATTR_UNIT_OF_MEASUREMENT: "not_a_valid_unit"}

    await assert_numerical_condition_unit_conversion(
        hass,
        condition="power.is_value",
        entity_id="sensor.test",
        pass_states=[
            {
                "state": "500",
                "attributes": {
                    "device_class": "power",
                    ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT,
                },
            }
        ],
        fail_states=[
            {
                "state": "100",
                "attributes": {
                    "device_class": "power",
                    ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT,
                },
            }
        ],
        numerical_condition_options=[
            {
                "threshold": {
                    "type": "between",
                    "value_min": {
                        "number": 0.2,
                        "unit_of_measurement": UnitOfPower.KILO_WATT,
                    },
                    "value_max": {
                        "number": 0.8,
                        "unit_of_measurement": UnitOfPower.KILO_WATT,
                    },
                }
            },
            {
                "threshold": {
                    "type": "between",
                    "value_min": {
                        "number": 200,
                        "unit_of_measurement": UnitOfPower.WATT,
                    },
                    "value_max": {
                        "number": 800,
                        "unit_of_measurement": UnitOfPower.WATT,
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
                {"state": "0.2", "attributes": _unit_kilowatt},  # 200W
                {"state": "0.8", "attributes": _unit_kilowatt},  # 800W
            ),
            (
                {"state": "200", "attributes": _unit_watt},
                {"state": "800", "attributes": _unit_watt},
            ),
        ],
        invalid_limit_entity_states=[
            (
                {"state": "0.2", "attributes": _unit_invalid},
                {"state": "0.8", "attributes": _unit_invalid},
            ),
            (
                {"state": "200", "attributes": _unit_invalid},
                {"state": "800", "attributes": _unit_invalid},
            ),
        ],
    )
