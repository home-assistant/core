"""Test air quality conditions."""

from typing import Any

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    assert_numerical_condition_unit_conversion,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_numerical_condition_above_below_all,
    parametrize_numerical_condition_above_below_any,
    parametrize_target_entities,
    target_entities,
)

_UGM3_UNIT_ATTRIBUTES = {
    ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
}
_PPB_UNIT_ATTRIBUTES = {ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION}
_PPM_UNIT_ATTRIBUTES = {ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_MILLION}


@pytest.fixture
async def target_binary_sensors(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple binary sensor entities associated with different targets."""
    return await target_entities(hass, "binary_sensor")


@pytest.fixture
async def target_sensors(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple sensor entities associated with different targets."""
    return await target_entities(hass, "sensor")


@pytest.mark.parametrize(
    "condition",
    [
        "air_quality.is_gas_detected",
        "air_quality.is_gas_cleared",
        "air_quality.is_co_detected",
        "air_quality.is_co_cleared",
        "air_quality.is_smoke_detected",
        "air_quality.is_smoke_cleared",
        "air_quality.is_co_value",
        "air_quality.is_co2_value",
        "air_quality.is_pm1_value",
        "air_quality.is_pm25_value",
        "air_quality.is_pm4_value",
        "air_quality.is_pm10_value",
        "air_quality.is_ozone_value",
        "air_quality.is_voc_value",
        "air_quality.is_voc_ratio_value",
        "air_quality.is_no_value",
        "air_quality.is_no2_value",
        "air_quality.is_n2o_value",
        "air_quality.is_so2_value",
    ],
)
async def test_air_quality_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the air quality conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="air_quality.is_gas_detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.GAS},
        ),
        *parametrize_condition_states_any(
            condition="air_quality.is_gas_cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.GAS},
        ),
        *parametrize_condition_states_any(
            condition="air_quality.is_co_detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.CO},
        ),
        *parametrize_condition_states_any(
            condition="air_quality.is_co_cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.CO},
        ),
        *parametrize_condition_states_any(
            condition="air_quality.is_smoke_detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.SMOKE
            },
        ),
        *parametrize_condition_states_any(
            condition="air_quality.is_smoke_cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.SMOKE
            },
        ),
    ],
)
async def test_air_quality_binary_condition_behavior_any(
    hass: HomeAssistant,
    target_binary_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the air quality binary sensor condition with 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_binary_sensors,
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
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="air_quality.is_gas_detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.GAS},
        ),
        *parametrize_condition_states_all(
            condition="air_quality.is_gas_cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.GAS},
        ),
        *parametrize_condition_states_all(
            condition="air_quality.is_co_detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.CO},
        ),
        *parametrize_condition_states_all(
            condition="air_quality.is_co_cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.CO},
        ),
        *parametrize_condition_states_all(
            condition="air_quality.is_smoke_detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.SMOKE
            },
        ),
        *parametrize_condition_states_all(
            condition="air_quality.is_smoke_cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.SMOKE
            },
        ),
    ],
)
async def test_air_quality_binary_condition_behavior_all(
    hass: HomeAssistant,
    target_binary_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the air quality binary sensor condition with 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_binary_sensors,
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
    [
        *parametrize_numerical_condition_above_below_any(
            "air_quality.is_co_value",
            device_class="carbon_monoxide",
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_any(
            "air_quality.is_ozone_value",
            device_class="ozone",
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_any(
            "air_quality.is_voc_value",
            device_class="volatile_organic_compounds",
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_any(
            "air_quality.is_voc_ratio_value",
            device_class="volatile_organic_compounds_parts",
            threshold_unit=CONCENTRATION_PARTS_PER_BILLION,
            unit_attributes=_PPB_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_any(
            "air_quality.is_no_value",
            device_class="nitrogen_monoxide",
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_any(
            "air_quality.is_no2_value",
            device_class="nitrogen_dioxide",
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_any(
            "air_quality.is_so2_value",
            device_class="sulphur_dioxide",
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_air_quality_numerical_with_unit_condition_behavior_any(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test air quality numerical conditions with unit conversion and 'any' behavior."""
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
    [
        *parametrize_numerical_condition_above_below_all(
            "air_quality.is_co_value",
            device_class="carbon_monoxide",
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_all(
            "air_quality.is_ozone_value",
            device_class="ozone",
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_all(
            "air_quality.is_voc_value",
            device_class="volatile_organic_compounds",
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_all(
            "air_quality.is_voc_ratio_value",
            device_class="volatile_organic_compounds_parts",
            threshold_unit=CONCENTRATION_PARTS_PER_BILLION,
            unit_attributes=_PPB_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_all(
            "air_quality.is_no_value",
            device_class="nitrogen_monoxide",
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_all(
            "air_quality.is_no2_value",
            device_class="nitrogen_dioxide",
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_all(
            "air_quality.is_so2_value",
            device_class="sulphur_dioxide",
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_air_quality_numerical_with_unit_condition_behavior_all(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test air quality numerical conditions with unit conversion and 'all' behavior."""
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
    parametrize_target_entities("sensor"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_numerical_condition_above_below_any(
            "air_quality.is_co2_value",
            device_class="carbon_dioxide",
            unit_attributes=_PPM_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_any(
            "air_quality.is_pm1_value",
            device_class="pm1",
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_any(
            "air_quality.is_pm25_value",
            device_class="pm25",
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_any(
            "air_quality.is_pm4_value",
            device_class="pm4",
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_any(
            "air_quality.is_pm10_value",
            device_class="pm10",
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_any(
            "air_quality.is_n2o_value",
            device_class="nitrous_oxide",
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_air_quality_numerical_no_unit_condition_behavior_any(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test air quality numerical conditions without unit conversion and 'any' behavior."""
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
    [
        *parametrize_numerical_condition_above_below_all(
            "air_quality.is_co2_value",
            device_class="carbon_dioxide",
            unit_attributes=_PPM_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_all(
            "air_quality.is_pm1_value",
            device_class="pm1",
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_all(
            "air_quality.is_pm25_value",
            device_class="pm25",
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_all(
            "air_quality.is_pm4_value",
            device_class="pm4",
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_all(
            "air_quality.is_pm10_value",
            device_class="pm10",
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_condition_above_below_all(
            "air_quality.is_n2o_value",
            device_class="nitrous_oxide",
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_air_quality_numerical_no_unit_condition_behavior_all(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test air quality numerical conditions without unit conversion and 'all' behavior."""
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
async def test_air_quality_condition_unit_conversion_co(
    hass: HomeAssistant,
) -> None:
    """Test that the CO condition converts units correctly."""
    _unit_ugm3 = {ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER}
    _unit_ppm = {ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_MILLION}
    _unit_invalid = {ATTR_UNIT_OF_MEASUREMENT: "not_a_valid_unit"}

    await assert_numerical_condition_unit_conversion(
        hass,
        condition="air_quality.is_co_value",
        entity_id="sensor.test",
        pass_states=[
            {
                "state": "500",
                "attributes": {
                    "device_class": "carbon_monoxide",
                    ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                },
            }
        ],
        fail_states=[
            {
                "state": "100",
                "attributes": {
                    "device_class": "carbon_monoxide",
                    ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                },
            }
        ],
        numerical_condition_options=[
            {
                "threshold": {
                    "type": "between",
                    "value_min": {
                        "number": 0.2,
                        "unit_of_measurement": CONCENTRATION_PARTS_PER_MILLION,
                    },
                    "value_max": {
                        "number": 0.8,
                        "unit_of_measurement": CONCENTRATION_PARTS_PER_MILLION,
                    },
                }
            },
            {
                "threshold": {
                    "type": "between",
                    "value_min": {
                        "number": 200,
                        "unit_of_measurement": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                    },
                    "value_max": {
                        "number": 800,
                        "unit_of_measurement": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
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
                {"state": "0.2", "attributes": _unit_ppm},
                {"state": "0.8", "attributes": _unit_ppm},
            ),
            (
                {"state": "200", "attributes": _unit_ugm3},
                {"state": "800", "attributes": _unit_ugm3},
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
