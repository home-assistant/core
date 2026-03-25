"""Test air quality trigger."""

from typing import Any

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

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
    "trigger_key",
    [
        "air_quality.gas_detected",
        "air_quality.gas_cleared",
        "air_quality.co_detected",
        "air_quality.co_cleared",
        "air_quality.smoke_detected",
        "air_quality.smoke_cleared",
        "air_quality.co_changed",
        "air_quality.co_crossed_threshold",
        "air_quality.co2_changed",
        "air_quality.co2_crossed_threshold",
        "air_quality.pm1_changed",
        "air_quality.pm1_crossed_threshold",
        "air_quality.pm25_changed",
        "air_quality.pm25_crossed_threshold",
        "air_quality.pm4_changed",
        "air_quality.pm4_crossed_threshold",
        "air_quality.pm10_changed",
        "air_quality.pm10_crossed_threshold",
        "air_quality.ozone_changed",
        "air_quality.ozone_crossed_threshold",
        "air_quality.voc_changed",
        "air_quality.voc_crossed_threshold",
        "air_quality.voc_ratio_changed",
        "air_quality.voc_ratio_crossed_threshold",
        "air_quality.no_changed",
        "air_quality.no_crossed_threshold",
        "air_quality.no2_changed",
        "air_quality.no2_crossed_threshold",
        "air_quality.n2o_changed",
        "air_quality.n2o_crossed_threshold",
        "air_quality.so2_changed",
        "air_quality.so2_crossed_threshold",
    ],
)
async def test_air_quality_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the air quality triggers are gated by the labs flag."""
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
            trigger="air_quality.co_detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.CO},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="air_quality.co_cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.CO},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="air_quality.gas_detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.GAS},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="air_quality.gas_cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.GAS},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="air_quality.smoke_detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.SMOKE
            },
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="air_quality.smoke_cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.SMOKE
            },
            trigger_from_none=False,
        ),
    ],
)
async def test_air_quality_trigger_binary_sensor_behavior_any(
    hass: HomeAssistant,
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test air quality triggers fire for binary_sensor entities with gas, CO, and smoke device classes."""
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
            trigger="air_quality.co_detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.CO},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="air_quality.co_cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.CO},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="air_quality.gas_detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.GAS},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="air_quality.gas_cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.GAS},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="air_quality.smoke_detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.SMOKE
            },
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="air_quality.smoke_cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.SMOKE
            },
            trigger_from_none=False,
        ),
    ],
)
async def test_air_quality_trigger_binary_sensor_behavior_first(
    hass: HomeAssistant,
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test air quality trigger fires on the first binary_sensor state change."""
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
            trigger="air_quality.co_detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.CO},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="air_quality.co_cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.CO},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="air_quality.gas_detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.GAS},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="air_quality.gas_cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: BinarySensorDeviceClass.GAS},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="air_quality.smoke_detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.SMOKE
            },
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="air_quality.smoke_cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.SMOKE
            },
            trigger_from_none=False,
        ),
    ],
)
async def test_air_quality_trigger_binary_sensor_behavior_last(
    hass: HomeAssistant,
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test air quality trigger fires when the last binary_sensor changes state."""
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
        # With unit conversion (µg/m³ base unit)
        *parametrize_numerical_state_value_changed_trigger_states(
            "air_quality.co_changed",
            device_class=SensorDeviceClass.CO,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.co_crossed_threshold",
            device_class=SensorDeviceClass.CO,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_changed_trigger_states(
            "air_quality.ozone_changed",
            device_class=SensorDeviceClass.OZONE,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.ozone_crossed_threshold",
            device_class=SensorDeviceClass.OZONE,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_changed_trigger_states(
            "air_quality.voc_changed",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.voc_crossed_threshold",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_changed_trigger_states(
            "air_quality.no_changed",
            device_class=SensorDeviceClass.NITROGEN_MONOXIDE,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.no_crossed_threshold",
            device_class=SensorDeviceClass.NITROGEN_MONOXIDE,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_changed_trigger_states(
            "air_quality.no2_changed",
            device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.no2_crossed_threshold",
            device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_changed_trigger_states(
            "air_quality.so2_changed",
            device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.so2_crossed_threshold",
            device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        # With unit conversion (ppb base unit)
        *parametrize_numerical_state_value_changed_trigger_states(
            "air_quality.voc_ratio_changed",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
            threshold_unit=CONCENTRATION_PARTS_PER_BILLION,
            unit_attributes=_PPB_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.voc_ratio_crossed_threshold",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
            threshold_unit=CONCENTRATION_PARTS_PER_BILLION,
            unit_attributes=_PPB_UNIT_ATTRIBUTES,
        ),
        # Without unit conversion (single-unit device classes)
        *parametrize_numerical_state_value_changed_trigger_states(
            "air_quality.co2_changed",
            device_class=SensorDeviceClass.CO2,
            unit_attributes=_PPM_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.co2_crossed_threshold",
            device_class=SensorDeviceClass.CO2,
            unit_attributes=_PPM_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_changed_trigger_states(
            "air_quality.pm1_changed",
            device_class=SensorDeviceClass.PM1,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.pm1_crossed_threshold",
            device_class=SensorDeviceClass.PM1,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_changed_trigger_states(
            "air_quality.pm25_changed",
            device_class=SensorDeviceClass.PM25,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.pm25_crossed_threshold",
            device_class=SensorDeviceClass.PM25,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_changed_trigger_states(
            "air_quality.pm4_changed",
            device_class=SensorDeviceClass.PM4,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.pm4_crossed_threshold",
            device_class=SensorDeviceClass.PM4,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_changed_trigger_states(
            "air_quality.pm10_changed",
            device_class=SensorDeviceClass.PM10,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.pm10_crossed_threshold",
            device_class=SensorDeviceClass.PM10,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_changed_trigger_states(
            "air_quality.n2o_changed",
            device_class=SensorDeviceClass.NITROUS_OXIDE,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.n2o_crossed_threshold",
            device_class=SensorDeviceClass.NITROUS_OXIDE,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_air_quality_trigger_sensor_behavior_any(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test air quality trigger fires for sensor entities."""
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
        # With unit conversion (µg/m³ base unit)
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.co_crossed_threshold",
            device_class=SensorDeviceClass.CO,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.ozone_crossed_threshold",
            device_class=SensorDeviceClass.OZONE,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.voc_crossed_threshold",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.no_crossed_threshold",
            device_class=SensorDeviceClass.NITROGEN_MONOXIDE,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.no2_crossed_threshold",
            device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.so2_crossed_threshold",
            device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        # With unit conversion (ppb base unit)
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.voc_ratio_crossed_threshold",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
            threshold_unit=CONCENTRATION_PARTS_PER_BILLION,
            unit_attributes=_PPB_UNIT_ATTRIBUTES,
        ),
        # Without unit conversion (single-unit device classes)
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.co2_crossed_threshold",
            device_class=SensorDeviceClass.CO2,
            unit_attributes=_PPM_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.pm1_crossed_threshold",
            device_class=SensorDeviceClass.PM1,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.pm25_crossed_threshold",
            device_class=SensorDeviceClass.PM25,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.pm4_crossed_threshold",
            device_class=SensorDeviceClass.PM4,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.pm10_crossed_threshold",
            device_class=SensorDeviceClass.PM10,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.n2o_crossed_threshold",
            device_class=SensorDeviceClass.NITROUS_OXIDE,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_air_quality_trigger_sensor_crossed_threshold_behavior_first(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test air quality crossed_threshold trigger fires on the first sensor state change."""
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
        # With unit conversion (µg/m³ base unit)
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.co_crossed_threshold",
            device_class=SensorDeviceClass.CO,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.ozone_crossed_threshold",
            device_class=SensorDeviceClass.OZONE,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.voc_crossed_threshold",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.no_crossed_threshold",
            device_class=SensorDeviceClass.NITROGEN_MONOXIDE,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.no2_crossed_threshold",
            device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.so2_crossed_threshold",
            device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
            threshold_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        # With unit conversion (ppb base unit)
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.voc_ratio_crossed_threshold",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
            threshold_unit=CONCENTRATION_PARTS_PER_BILLION,
            unit_attributes=_PPB_UNIT_ATTRIBUTES,
        ),
        # Without unit conversion (single-unit device classes)
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.co2_crossed_threshold",
            device_class=SensorDeviceClass.CO2,
            unit_attributes=_PPM_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.pm1_crossed_threshold",
            device_class=SensorDeviceClass.PM1,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.pm25_crossed_threshold",
            device_class=SensorDeviceClass.PM25,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.pm4_crossed_threshold",
            device_class=SensorDeviceClass.PM4,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.pm10_crossed_threshold",
            device_class=SensorDeviceClass.PM10,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
        *parametrize_numerical_state_value_crossed_threshold_trigger_states(
            "air_quality.n2o_crossed_threshold",
            device_class=SensorDeviceClass.NITROUS_OXIDE,
            unit_attributes=_UGM3_UNIT_ATTRIBUTES,
        ),
    ],
)
async def test_air_quality_trigger_sensor_crossed_threshold_behavior_last(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test air quality crossed_threshold trigger fires when the last sensor changes state."""
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
async def test_air_quality_trigger_unit_conversion_co_ppm_to_ugm3(
    hass: HomeAssistant,
) -> None:
    """Test CO crossed_threshold trigger converts sensor value from ppm to μg/m³."""
    calls: list[str] = []
    entity_id = "sensor.test_co"

    # Sensor reports in ppm, trigger threshold is in μg/m³ (fixed unit for CO)
    # 1 ppm CO ≈ 1164 μg/m³ at 20°C, 1 atm
    hass.states.async_set(
        entity_id,
        "0.5",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.CO,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_MILLION,
        },
    )
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        "air_quality.co_crossed_threshold",
        {
            "threshold": {
                "type": "above",
                "value": {"number": 1000, "unit_of_measurement": "μg/m³"},
            }
        },
        {CONF_ENTITY_ID: [entity_id]},
        calls,
    )

    # 0.5 ppm ≈ 582 μg/m³, which is below 1000 μg/m³ - should NOT trigger
    hass.states.async_set(
        entity_id,
        "0.5",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.CO,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_MILLION,
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 0

    # 1 ppm ≈ 1164 μg/m³, which is above 1000 μg/m³ - should trigger
    hass.states.async_set(
        entity_id,
        "1",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.CO,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_MILLION,
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    calls.clear()
