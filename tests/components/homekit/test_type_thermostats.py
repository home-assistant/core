"""Test different accessory types: Thermostats."""
from unittest.mock import patch

from pyhap.const import HAP_REPR_AID, HAP_REPR_CHARS, HAP_REPR_IID, HAP_REPR_VALUE
import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_STEP,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_HUMIDITY,
    DOMAIN as DOMAIN_CLIMATE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    FAN_ON,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_SWING_MODE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.homekit.const import (
    ATTR_VALUE,
    CHAR_CURRENT_FAN_STATE,
    CHAR_ROTATION_SPEED,
    CHAR_SWING_MODE,
    CHAR_TARGET_FAN_STATE,
    DEFAULT_MAX_TEMP_WATER_HEATER,
    DEFAULT_MIN_TEMP_WATER_HEATER,
    PROP_MAX_VALUE,
    PROP_MIN_STEP,
    PROP_MIN_VALUE,
)
from homeassistant.components.homekit.type_thermostats import (
    HC_HEAT_COOL_AUTO,
    HC_HEAT_COOL_COOL,
    HC_HEAT_COOL_HEAT,
    HC_HEAT_COOL_OFF,
    Thermostat,
    WaterHeater,
)
from homeassistant.components.water_heater import DOMAIN as DOMAIN_WATER_HEATER
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    CONF_TEMPERATURE_UNIT,
    EVENT_HOMEASSISTANT_START,
    UnitOfTemperature,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import async_mock_service


async def test_thermostat(hass: HomeAssistant, hk_driver, events) -> None:
    """Test if accessory and HA are updated accordingly."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [
            HVACMode.HEAT,
            HVACMode.HEAT_COOL,
            HVACMode.FAN_ONLY,
            HVACMode.COOL,
            HVACMode.OFF,
            HVACMode.AUTO,
        ],
    }

    hass.states.async_set(
        entity_id,
        HVACMode.OFF,
        base_attrs,
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 1
    assert acc.category == 9  # Thermostat

    state = hass.states.get(entity_id)
    assert state
    assert acc.get_temperature_range(state) == (7.0, 35.0)
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 0
    assert acc.char_current_temp.value == 21.0
    assert acc.char_target_temp.value == 21.0
    assert acc.char_display_units.value == 0
    assert acc.char_cooling_thresh_temp is None
    assert acc.char_heating_thresh_temp is None
    assert acc.char_target_humidity is None
    assert acc.char_current_humidity is None

    assert acc.char_target_temp.properties[PROP_MAX_VALUE] == DEFAULT_MAX_TEMP
    assert acc.char_target_temp.properties[PROP_MIN_VALUE] == 7.0
    assert acc.char_target_temp.properties[PROP_MIN_STEP] == 0.1

    hass.states.async_set(
        entity_id,
        HVACMode.HEAT,
        {
            **base_attrs,
            ATTR_TEMPERATURE: 22.2,
            ATTR_CURRENT_TEMPERATURE: 17.8,
            ATTR_HVAC_ACTION: HVACAction.HEATING,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 22.2
    assert acc.char_current_heat_cool.value == 1
    assert acc.char_target_heat_cool.value == 1
    assert acc.char_current_temp.value == 17.8
    assert acc.char_display_units.value == 0

    hass.states.async_set(
        entity_id,
        HVACMode.HEAT,
        {
            **base_attrs,
            ATTR_TEMPERATURE: 22.0,
            ATTR_CURRENT_TEMPERATURE: 23.0,
            ATTR_HVAC_ACTION: HVACAction.IDLE,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 1
    assert acc.char_current_temp.value == 23.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(
        entity_id,
        HVACMode.FAN_ONLY,
        {
            **base_attrs,
            ATTR_TEMPERATURE: 20.0,
            ATTR_CURRENT_TEMPERATURE: 25.0,
            ATTR_HVAC_ACTION: HVACAction.COOLING,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 20.0
    assert acc.char_current_heat_cool.value == 2
    assert acc.char_target_heat_cool.value == 2
    assert acc.char_current_temp.value == 25.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(
        entity_id,
        HVACMode.COOL,
        {
            **base_attrs,
            ATTR_TEMPERATURE: 20.0,
            ATTR_CURRENT_TEMPERATURE: 19.0,
            ATTR_HVAC_ACTION: HVACAction.IDLE,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 20.0
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 2
    assert acc.char_current_temp.value == 19.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(
        entity_id,
        HVACMode.OFF,
        {**base_attrs, ATTR_TEMPERATURE: 22.0, ATTR_CURRENT_TEMPERATURE: 18.0},
    )
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 0
    assert acc.char_current_temp.value == 18.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(
        entity_id,
        HVACMode.AUTO,
        {
            **base_attrs,
            ATTR_TEMPERATURE: 22.0,
            ATTR_CURRENT_TEMPERATURE: 18.0,
            ATTR_HVAC_ACTION: HVACAction.HEATING,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 1
    assert acc.char_target_heat_cool.value == 3
    assert acc.char_current_temp.value == 18.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(
        entity_id,
        HVACMode.HEAT_COOL,
        {
            **base_attrs,
            ATTR_TEMPERATURE: 22.0,
            ATTR_CURRENT_TEMPERATURE: 25.0,
            ATTR_HVAC_ACTION: HVACAction.COOLING,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 2
    assert acc.char_target_heat_cool.value == 3
    assert acc.char_current_temp.value == 25.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(
        entity_id,
        HVACMode.AUTO,
        {
            **base_attrs,
            ATTR_TEMPERATURE: 22.0,
            ATTR_CURRENT_TEMPERATURE: 22.0,
            ATTR_HVAC_ACTION: HVACAction.IDLE,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 3
    assert acc.char_current_temp.value == 22.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(
        entity_id,
        HVACMode.FAN_ONLY,
        {
            **base_attrs,
            ATTR_TEMPERATURE: 22.0,
            ATTR_CURRENT_TEMPERATURE: 22.0,
            ATTR_HVAC_ACTION: HVACAction.FAN,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 2
    assert acc.char_target_heat_cool.value == 2
    assert acc.char_current_temp.value == 22.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(
        entity_id,
        HVACMode.DRY,
        {
            **base_attrs,
            ATTR_TEMPERATURE: 22.0,
            ATTR_CURRENT_TEMPERATURE: 22.0,
            ATTR_HVAC_ACTION: HVACAction.DRYING,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 2
    assert acc.char_target_heat_cool.value == 2
    assert acc.char_current_temp.value == 22.0
    assert acc.char_display_units.value == 0

    # Set from HomeKit
    call_set_temperature = async_mock_service(hass, DOMAIN_CLIMATE, "set_temperature")
    call_set_hvac_mode = async_mock_service(hass, DOMAIN_CLIMATE, "set_hvac_mode")

    char_target_temp_iid = acc.char_target_temp.to_HAP()[HAP_REPR_IID]
    char_heat_cool_iid = acc.char_target_heat_cool.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_temp_iid,
                    HAP_REPR_VALUE: 19.0,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_set_temperature
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TEMPERATURE] == 19.0
    assert acc.char_target_temp.value == 19.0
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "TargetTemperature to 19.0°C"

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_heat_cool_iid,
                    HAP_REPR_VALUE: 2,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert not call_set_hvac_mode

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_heat_cool_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_set_hvac_mode
    assert call_set_hvac_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVACMode.HEAT
    assert acc.char_target_heat_cool.value == 1
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == "TargetHeatingCoolingState to 1"

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_heat_cool_iid,
                    HAP_REPR_VALUE: 3,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_set_hvac_mode
    assert call_set_hvac_mode[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_hvac_mode[1].data[ATTR_HVAC_MODE] == HVACMode.HEAT_COOL
    assert acc.char_target_heat_cool.value == 3
    assert len(events) == 3
    assert events[-1].data[ATTR_VALUE] == "TargetHeatingCoolingState to 3"


async def test_thermostat_auto(hass: HomeAssistant, hk_driver, events) -> None:
    """Test if accessory and HA are updated accordingly."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
        ATTR_HVAC_MODES: [
            HVACMode.HEAT,
            HVACMode.HEAT_COOL,
            HVACMode.FAN_ONLY,
            HVACMode.COOL,
            HVACMode.OFF,
            HVACMode.AUTO,
        ],
    }
    # support_auto = True
    hass.states.async_set(
        entity_id,
        HVACMode.OFF,
        base_attrs,
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_heating_thresh_temp.value == 19.0

    assert acc.char_cooling_thresh_temp.properties[PROP_MAX_VALUE] == DEFAULT_MAX_TEMP
    assert acc.char_cooling_thresh_temp.properties[PROP_MIN_VALUE] == 7.0
    assert acc.char_cooling_thresh_temp.properties[PROP_MIN_STEP] == 0.1
    assert acc.char_heating_thresh_temp.properties[PROP_MAX_VALUE] == DEFAULT_MAX_TEMP
    assert acc.char_heating_thresh_temp.properties[PROP_MIN_VALUE] == 7.0
    assert acc.char_heating_thresh_temp.properties[PROP_MIN_STEP] == 0.1

    hass.states.async_set(
        entity_id,
        HVACMode.HEAT_COOL,
        {
            **base_attrs,
            ATTR_TARGET_TEMP_HIGH: 22.0,
            ATTR_TARGET_TEMP_LOW: 20.0,
            ATTR_CURRENT_TEMPERATURE: 18.0,
            ATTR_HVAC_ACTION: HVACAction.HEATING,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_heating_thresh_temp.value == 20.0
    assert acc.char_cooling_thresh_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 1
    assert acc.char_target_heat_cool.value == 3
    assert acc.char_current_temp.value == 18.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(
        entity_id,
        HVACMode.COOL,
        {
            **base_attrs,
            ATTR_TARGET_TEMP_HIGH: 23.0,
            ATTR_TARGET_TEMP_LOW: 19.0,
            ATTR_CURRENT_TEMPERATURE: 24.0,
            ATTR_HVAC_ACTION: HVACAction.COOLING,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_heating_thresh_temp.value == 19.0
    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_current_heat_cool.value == 2
    assert acc.char_target_heat_cool.value == 2
    assert acc.char_current_temp.value == 24.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(
        entity_id,
        HVACMode.AUTO,
        {
            **base_attrs,
            ATTR_TARGET_TEMP_HIGH: 23.0,
            ATTR_TARGET_TEMP_LOW: 19.0,
            ATTR_CURRENT_TEMPERATURE: 21.0,
            ATTR_HVAC_ACTION: HVACAction.IDLE,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_heating_thresh_temp.value == 19.0
    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 3
    assert acc.char_current_temp.value == 21.0
    assert acc.char_display_units.value == 0

    # Set from HomeKit
    call_set_temperature = async_mock_service(hass, DOMAIN_CLIMATE, "set_temperature")

    char_heating_thresh_temp_iid = acc.char_heating_thresh_temp.to_HAP()[HAP_REPR_IID]
    char_cooling_thresh_temp_iid = acc.char_cooling_thresh_temp.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_heating_thresh_temp_iid,
                    HAP_REPR_VALUE: 20.0,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_cooling_thresh_temp_iid,
                    HAP_REPR_VALUE: 25.0,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert call_set_temperature[0]
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TARGET_TEMP_LOW] == 20.0
    assert call_set_temperature[0].data[ATTR_TARGET_TEMP_HIGH] == 25.0
    assert acc.char_heating_thresh_temp.value == 20.0
    assert acc.char_cooling_thresh_temp.value == 25.0
    assert len(events) == 1
    assert (
        events[-1].data[ATTR_VALUE]
        == "CoolingThresholdTemperature to 25.0°C, HeatingThresholdTemperature to 20.0°C"
    )


async def test_thermostat_mode_and_temp_change(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test if accessory where the mode and temp change in the same call."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
        ATTR_HVAC_MODES: [
            HVACMode.HEAT,
            HVACMode.HEAT_COOL,
            HVACMode.FAN_ONLY,
            HVACMode.COOL,
            HVACMode.OFF,
            HVACMode.AUTO,
        ],
    }
    # support_auto = True
    hass.states.async_set(
        entity_id,
        HVACMode.OFF,
        base_attrs,
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_heating_thresh_temp.value == 19.0

    assert acc.char_cooling_thresh_temp.properties[PROP_MAX_VALUE] == DEFAULT_MAX_TEMP
    assert acc.char_cooling_thresh_temp.properties[PROP_MIN_VALUE] == 7.0
    assert acc.char_cooling_thresh_temp.properties[PROP_MIN_STEP] == 0.1
    assert acc.char_heating_thresh_temp.properties[PROP_MAX_VALUE] == DEFAULT_MAX_TEMP
    assert acc.char_heating_thresh_temp.properties[PROP_MIN_VALUE] == 7.0
    assert acc.char_heating_thresh_temp.properties[PROP_MIN_STEP] == 0.1

    hass.states.async_set(
        entity_id,
        HVACMode.COOL,
        {
            **base_attrs,
            ATTR_TARGET_TEMP_HIGH: 23.0,
            ATTR_TARGET_TEMP_LOW: 19.0,
            ATTR_CURRENT_TEMPERATURE: 21.0,
            ATTR_HVAC_ACTION: HVACAction.COOLING,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_heating_thresh_temp.value == 19.0
    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_current_heat_cool.value == HC_HEAT_COOL_COOL
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_COOL
    assert acc.char_current_temp.value == 21.0
    assert acc.char_display_units.value == 0

    # Set from HomeKit
    call_set_temperature = async_mock_service(hass, DOMAIN_CLIMATE, "set_temperature")
    call_set_hvac_mode = async_mock_service(hass, DOMAIN_CLIMATE, "set_hvac_mode")

    char_heating_thresh_temp_iid = acc.char_heating_thresh_temp.to_HAP()[HAP_REPR_IID]
    char_cooling_thresh_temp_iid = acc.char_cooling_thresh_temp.to_HAP()[HAP_REPR_IID]
    char_target_heat_cool_iid = acc.char_target_heat_cool.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_heating_thresh_temp_iid,
                    HAP_REPR_VALUE: 20.0,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_cooling_thresh_temp_iid,
                    HAP_REPR_VALUE: 25.0,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_heat_cool_iid,
                    HAP_REPR_VALUE: HC_HEAT_COOL_AUTO,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert call_set_hvac_mode[0]
    assert call_set_hvac_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVACMode.HEAT_COOL
    assert call_set_temperature[0]
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TARGET_TEMP_LOW] == 20.0
    assert call_set_temperature[0].data[ATTR_TARGET_TEMP_HIGH] == 25.0
    assert acc.char_heating_thresh_temp.value == 20.0
    assert acc.char_cooling_thresh_temp.value == 25.0
    assert len(events) == 2
    assert events[-2].data[ATTR_VALUE] == "TargetHeatingCoolingState to 3"
    assert (
        events[-1].data[ATTR_VALUE]
        == "TargetHeatingCoolingState to 3, CoolingThresholdTemperature to 25.0°C, HeatingThresholdTemperature to 20.0°C"
    )


async def test_thermostat_humidity(hass: HomeAssistant, hk_driver, events) -> None:
    """Test if accessory and HA are updated accordingly with humidity."""
    entity_id = "climate.test"
    base_attrs = {ATTR_SUPPORTED_FEATURES: 4}
    # support_auto = True
    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_target_humidity.value == 50
    assert acc.char_current_humidity.value == 50

    assert acc.char_target_humidity.properties[PROP_MIN_VALUE] == DEFAULT_MIN_HUMIDITY

    hass.states.async_set(
        entity_id,
        HVACMode.HEAT_COOL,
        {**base_attrs, ATTR_HUMIDITY: 65, ATTR_CURRENT_HUMIDITY: 40},
    )
    await hass.async_block_till_done()
    assert acc.char_current_humidity.value == 40
    assert acc.char_target_humidity.value == 65

    hass.states.async_set(
        entity_id,
        HVACMode.COOL,
        {**base_attrs, ATTR_HUMIDITY: 35, ATTR_CURRENT_HUMIDITY: 70},
    )
    await hass.async_block_till_done()
    assert acc.char_current_humidity.value == 70
    assert acc.char_target_humidity.value == 35

    # Set from HomeKit
    call_set_humidity = async_mock_service(hass, DOMAIN_CLIMATE, "set_humidity")

    char_target_humidity_iid = acc.char_target_humidity.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_humidity_iid,
                    HAP_REPR_VALUE: 35,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert call_set_humidity[0]
    assert call_set_humidity[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_humidity[0].data[ATTR_HUMIDITY] == 35
    assert acc.char_target_humidity.value == 35
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "35%"


async def test_thermostat_humidity_with_target_humidity(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test if accessory and HA are updated accordingly with humidity without target hudmidity.

    This test is for thermostats that do not support target humidity but
    have a current humidity sensor.
    """
    entity_id = "climate.test"

    # support_auto = True
    hass.states.async_set(entity_id, HVACMode.OFF, {ATTR_CURRENT_HUMIDITY: 40})
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_current_humidity.value == 40
    hass.states.async_set(entity_id, HVACMode.HEAT_COOL, {ATTR_CURRENT_HUMIDITY: 65})
    await hass.async_block_till_done()
    assert acc.char_current_humidity.value == 65


async def test_thermostat_power_state(hass: HomeAssistant, hk_driver, events) -> None:
    """Test if accessory and HA are updated accordingly."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: 4096,
        ATTR_TEMPERATURE: 23.0,
        ATTR_CURRENT_TEMPERATURE: 18.0,
        ATTR_HVAC_ACTION: HVACAction.HEATING,
        ATTR_HVAC_MODES: [
            HVACMode.HEAT_COOL,
            HVACMode.COOL,
            HVACMode.AUTO,
            HVACMode.HEAT,
            HVACMode.OFF,
        ],
    }
    # SUPPORT_ON_OFF = True
    hass.states.async_set(
        entity_id,
        HVACMode.HEAT,
        base_attrs,
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_current_heat_cool.value == 1
    assert acc.char_target_heat_cool.value == 1

    hass.states.async_set(
        entity_id,
        HVACMode.OFF,
        {
            **base_attrs,
            ATTR_TEMPERATURE: 23.0,
            ATTR_CURRENT_TEMPERATURE: 18.0,
            ATTR_HVAC_ACTION: HVACAction.IDLE,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 0

    hass.states.async_set(
        entity_id,
        HVACMode.OFF,
        {
            **base_attrs,
            ATTR_TEMPERATURE: 23.0,
            ATTR_CURRENT_TEMPERATURE: 18.0,
            ATTR_HVAC_ACTION: HVACAction.IDLE,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 0

    # Set from HomeKit
    call_set_hvac_mode = async_mock_service(hass, DOMAIN_CLIMATE, "set_hvac_mode")

    char_target_heat_cool_iid = acc.char_target_heat_cool.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_heat_cool_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert call_set_hvac_mode
    assert call_set_hvac_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVACMode.HEAT
    assert acc.char_target_heat_cool.value == 1
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "TargetHeatingCoolingState to 1"

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_heat_cool_iid,
                    HAP_REPR_VALUE: 2,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert call_set_hvac_mode
    assert call_set_hvac_mode[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_hvac_mode[1].data[ATTR_HVAC_MODE] == HVACMode.COOL
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == "TargetHeatingCoolingState to 2"
    assert acc.char_target_heat_cool.value == 2


async def test_thermostat_fahrenheit(hass: HomeAssistant, hk_driver, events) -> None:
    """Test if accessory and HA are updated accordingly."""
    entity_id = "climate.test"

    # support_ = True
    hass.states.async_set(
        entity_id,
        HVACMode.OFF,
        {
            ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        },
    )
    await hass.async_block_till_done()
    with patch.object(
        hass.config.units, CONF_TEMPERATURE_UNIT, new=UnitOfTemperature.FAHRENHEIT
    ):
        acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)
    await acc.run()
    await hass.async_block_till_done()

    hass.states.async_set(
        entity_id,
        HVACMode.HEAT_COOL,
        {
            ATTR_TARGET_TEMP_HIGH: 75.2,
            ATTR_TARGET_TEMP_LOW: 68.1,
            ATTR_TEMPERATURE: 71.6,
            ATTR_CURRENT_TEMPERATURE: 73.4,
            ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state
    assert acc.get_temperature_range(state) == (7.0, 35.0)
    assert acc.char_heating_thresh_temp.value == 20.1
    assert acc.char_cooling_thresh_temp.value == 24.0
    assert acc.char_current_temp.value == 23.0
    assert acc.char_target_temp.value == 22.0
    assert acc.char_display_units.value == 1

    # Set from HomeKit
    call_set_temperature = async_mock_service(hass, DOMAIN_CLIMATE, "set_temperature")

    char_cooling_thresh_temp_iid = acc.char_cooling_thresh_temp.to_HAP()[HAP_REPR_IID]
    char_heating_thresh_temp_iid = acc.char_heating_thresh_temp.to_HAP()[HAP_REPR_IID]
    char_target_temp_iid = acc.char_target_temp.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_cooling_thresh_temp_iid,
                    HAP_REPR_VALUE: 23,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert call_set_temperature[0]
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TARGET_TEMP_HIGH] == 73.5
    assert call_set_temperature[0].data[ATTR_TARGET_TEMP_LOW] == 68
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "CoolingThresholdTemperature to 23°C"

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_heating_thresh_temp_iid,
                    HAP_REPR_VALUE: 22,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert call_set_temperature[1]
    assert call_set_temperature[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[1].data[ATTR_TARGET_TEMP_HIGH] == 73.5
    assert call_set_temperature[1].data[ATTR_TARGET_TEMP_LOW] == 71.5
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == "HeatingThresholdTemperature to 22°C"

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_temp_iid,
                    HAP_REPR_VALUE: 24.0,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_set_temperature[2]
    assert call_set_temperature[2].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[2].data[ATTR_TEMPERATURE] == 75.0
    assert len(events) == 3
    assert events[-1].data[ATTR_VALUE] == "TargetTemperature to 24.0°C"


async def test_thermostat_get_temperature_range(hass: HomeAssistant, hk_driver) -> None:
    """Test if temperature range is evaluated correctly."""
    entity_id = "climate.test"

    hass.states.async_set(entity_id, HVACMode.OFF)
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 2, None)

    hass.states.async_set(
        entity_id, HVACMode.OFF, {ATTR_MIN_TEMP: 20, ATTR_MAX_TEMP: 25}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state
    assert acc.get_temperature_range(state) == (20, 25)

    acc._unit = UnitOfTemperature.FAHRENHEIT
    hass.states.async_set(
        entity_id, HVACMode.OFF, {ATTR_MIN_TEMP: 60, ATTR_MAX_TEMP: 70}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state
    assert acc.get_temperature_range(state) == (15.5, 21.0)


async def test_thermostat_temperature_step_whole(
    hass: HomeAssistant, hk_driver
) -> None:
    """Test climate device with single digit precision."""
    entity_id = "climate.test"

    hass.states.async_set(entity_id, HVACMode.OFF, {ATTR_TARGET_TEMP_STEP: 1})
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_target_temp.properties[PROP_MIN_STEP] == 0.1


async def test_thermostat_restore(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, hk_driver, events
) -> None:
    """Test setting up an entity from state in the event registry."""
    hass.state = CoreState.not_running

    entity_registry.async_get_or_create(
        "climate", "generic", "1234", suggested_object_id="simple"
    )
    entity_registry.async_get_or_create(
        "climate",
        "generic",
        "9012",
        suggested_object_id="all_info_set",
        capabilities={
            ATTR_MIN_TEMP: 60,
            ATTR_MAX_TEMP: 70,
            ATTR_HVAC_MODES: [HVACMode.HEAT_COOL, HVACMode.OFF],
        },
        supported_features=0,
        original_device_class="mock-device-class",
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START, {})
    await hass.async_block_till_done()

    entity_id = "climate.simple"
    hass.states.async_set(entity_id, HVACMode.OFF)

    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 2, None)
    assert acc.category == 9
    state = hass.states.get(entity_id)
    assert state
    assert acc.get_temperature_range(state) == (7, 35)
    assert set(acc.char_target_heat_cool.properties["ValidValues"].keys()) == {
        "cool",
        "heat",
        "heat_cool",
        "off",
    }

    entity_id = "climate.all_info_set"
    state = hass.states.get(entity_id)
    assert state

    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 3, None)
    assert acc.category == 9
    assert acc.get_temperature_range(state) == (60.0, 70.0)
    assert set(acc.char_target_heat_cool.properties["ValidValues"].keys()) == {
        "heat_cool",
        "off",
    }


async def test_thermostat_hvac_modes(hass: HomeAssistant, hk_driver) -> None:
    """Test if unsupported HVAC modes are deactivated in HomeKit."""
    entity_id = "climate.test"

    hass.states.async_set(
        entity_id, HVACMode.OFF, {ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.OFF]}
    )

    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()
    hap = acc.char_target_heat_cool.to_HAP()
    assert hap["valid-values"] == [0, 1]
    assert acc.char_target_heat_cool.value == 0

    with pytest.raises(ValueError):
        acc.char_target_heat_cool.set_value(3)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 0

    acc.char_target_heat_cool.set_value(1)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1

    with pytest.raises(ValueError):
        acc.char_target_heat_cool.set_value(2)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1


async def test_thermostat_hvac_modes_with_auto_heat_cool(
    hass: HomeAssistant, hk_driver
) -> None:
    """Test we get heat cool over auto."""
    entity_id = "climate.test"

    hass.states.async_set(
        entity_id,
        HVACMode.OFF,
        {
            ATTR_HVAC_MODES: [
                HVACMode.HEAT_COOL,
                HVACMode.AUTO,
                HVACMode.HEAT,
                HVACMode.OFF,
            ]
        },
    )
    call_set_hvac_mode = async_mock_service(hass, DOMAIN_CLIMATE, "set_hvac_mode")
    await hass.async_block_till_done()

    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()
    hap = acc.char_target_heat_cool.to_HAP()
    assert hap["valid-values"] == [0, 1, 3]
    assert acc.char_target_heat_cool.value == 0

    acc.char_target_heat_cool.set_value(3)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 3

    acc.char_target_heat_cool.set_value(1)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1

    with pytest.raises(ValueError):
        acc.char_target_heat_cool.set_value(2)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1

    char_target_heat_cool_iid = acc.char_target_heat_cool.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_heat_cool_iid,
                    HAP_REPR_VALUE: 3,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert call_set_hvac_mode
    assert call_set_hvac_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVACMode.HEAT_COOL
    assert acc.char_target_heat_cool.value == 3


async def test_thermostat_hvac_modes_with_auto_no_heat_cool(
    hass: HomeAssistant, hk_driver
) -> None:
    """Test we get auto when there is no heat cool."""
    entity_id = "climate.test"

    hass.states.async_set(
        entity_id,
        HVACMode.HEAT,
        {ATTR_HVAC_MODES: [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]},
    )
    call_set_hvac_mode = async_mock_service(hass, DOMAIN_CLIMATE, "set_hvac_mode")
    await hass.async_block_till_done()

    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()
    hap = acc.char_target_heat_cool.to_HAP()
    assert hap["valid-values"] == [0, 1, 3]
    assert acc.char_target_heat_cool.value == 1

    acc.char_target_heat_cool.set_value(3)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 3

    acc.char_target_heat_cool.set_value(1)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1

    with pytest.raises(ValueError):
        acc.char_target_heat_cool.set_value(2)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1

    char_target_heat_cool_iid = acc.char_target_heat_cool.to_HAP()[HAP_REPR_IID]
    call_set_hvac_mode = async_mock_service(hass, DOMAIN_CLIMATE, "set_hvac_mode")
    await hass.async_block_till_done()
    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_heat_cool_iid,
                    HAP_REPR_VALUE: 3,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert call_set_hvac_mode
    assert call_set_hvac_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVACMode.AUTO
    assert acc.char_target_heat_cool.value == 3


async def test_thermostat_hvac_modes_with_auto_only(
    hass: HomeAssistant, hk_driver
) -> None:
    """Test if unsupported HVAC modes are deactivated in HomeKit."""
    entity_id = "climate.test"

    hass.states.async_set(
        entity_id, HVACMode.AUTO, {ATTR_HVAC_MODES: [HVACMode.AUTO, HVACMode.OFF]}
    )

    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()
    hap = acc.char_target_heat_cool.to_HAP()
    assert hap["valid-values"] == [0, 3]
    assert acc.char_target_heat_cool.value == 3

    acc.char_target_heat_cool.set_value(3)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 3

    with pytest.raises(ValueError):
        acc.char_target_heat_cool.set_value(1)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 3

    with pytest.raises(ValueError):
        acc.char_target_heat_cool.set_value(2)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 3

    char_target_heat_cool_iid = acc.char_target_heat_cool.to_HAP()[HAP_REPR_IID]
    call_set_hvac_mode = async_mock_service(hass, DOMAIN_CLIMATE, "set_hvac_mode")
    await hass.async_block_till_done()
    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_heat_cool_iid,
                    HAP_REPR_VALUE: HC_HEAT_COOL_HEAT,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert call_set_hvac_mode
    assert call_set_hvac_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVACMode.AUTO


async def test_thermostat_hvac_modes_with_heat_only(
    hass: HomeAssistant, hk_driver
) -> None:
    """Test if unsupported HVAC modes are deactivated in HomeKit and siri calls get converted to heat."""
    entity_id = "climate.test"

    hass.states.async_set(
        entity_id, HVACMode.HEAT, {ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.OFF]}
    )

    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()
    hap = acc.char_target_heat_cool.to_HAP()
    assert hap["valid-values"] == [HC_HEAT_COOL_OFF, HC_HEAT_COOL_HEAT]
    assert acc.char_target_heat_cool.allow_invalid_client_values is True
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_HEAT

    acc.char_target_heat_cool.set_value(HC_HEAT_COOL_HEAT)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_HEAT

    with pytest.raises(ValueError):
        acc.char_target_heat_cool.set_value(HC_HEAT_COOL_COOL)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_HEAT

    with pytest.raises(ValueError):
        acc.char_target_heat_cool.set_value(HC_HEAT_COOL_AUTO)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_HEAT

    char_target_heat_cool_iid = acc.char_target_heat_cool.to_HAP()[HAP_REPR_IID]
    call_set_hvac_mode = async_mock_service(hass, DOMAIN_CLIMATE, "set_hvac_mode")
    await hass.async_block_till_done()
    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_heat_cool_iid,
                    HAP_REPR_VALUE: HC_HEAT_COOL_AUTO,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert call_set_hvac_mode
    assert call_set_hvac_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVACMode.HEAT

    acc.char_target_heat_cool.client_update_value(HC_HEAT_COOL_OFF)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_OFF
    hass.states.async_set(
        entity_id, HVACMode.OFF, {ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.OFF]}
    )
    await hass.async_block_till_done()

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_heat_cool_iid,
                    HAP_REPR_VALUE: HC_HEAT_COOL_AUTO,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_HEAT


async def test_thermostat_hvac_modes_with_cool_only(
    hass: HomeAssistant, hk_driver
) -> None:
    """Test if unsupported HVAC modes are deactivated in HomeKit and siri calls get converted to cool."""
    entity_id = "climate.test"

    hass.states.async_set(
        entity_id, HVACMode.COOL, {ATTR_HVAC_MODES: [HVACMode.COOL, HVACMode.OFF]}
    )

    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()
    hap = acc.char_target_heat_cool.to_HAP()
    assert hap["valid-values"] == [HC_HEAT_COOL_OFF, HC_HEAT_COOL_COOL]
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_COOL

    acc.char_target_heat_cool.set_value(HC_HEAT_COOL_COOL)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_COOL

    with pytest.raises(ValueError):
        acc.char_target_heat_cool.set_value(HC_HEAT_COOL_AUTO)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_COOL

    with pytest.raises(ValueError):
        acc.char_target_heat_cool.set_value(HC_HEAT_COOL_HEAT)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_COOL

    char_target_heat_cool_iid = acc.char_target_heat_cool.to_HAP()[HAP_REPR_IID]
    call_set_hvac_mode = async_mock_service(hass, DOMAIN_CLIMATE, "set_hvac_mode")
    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_heat_cool_iid,
                    HAP_REPR_VALUE: HC_HEAT_COOL_AUTO,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert call_set_hvac_mode
    assert call_set_hvac_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVACMode.COOL


async def test_thermostat_hvac_modes_with_heat_cool_only(
    hass: HomeAssistant, hk_driver
) -> None:
    """Test if unsupported HVAC modes are deactivated in HomeKit and siri calls get converted to heat or cool."""
    entity_id = "climate.test"

    hass.states.async_set(
        entity_id,
        HVACMode.COOL,
        {
            ATTR_CURRENT_TEMPERATURE: 30,
            ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        },
    )

    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()
    hap = acc.char_target_heat_cool.to_HAP()
    assert hap["valid-values"] == [
        HC_HEAT_COOL_OFF,
        HC_HEAT_COOL_HEAT,
        HC_HEAT_COOL_COOL,
    ]
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_COOL

    acc.char_target_heat_cool.set_value(HC_HEAT_COOL_COOL)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_COOL

    with pytest.raises(ValueError):
        acc.char_target_heat_cool.set_value(HC_HEAT_COOL_AUTO)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_COOL

    acc.char_target_heat_cool.set_value(HC_HEAT_COOL_HEAT)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_HEAT
    char_target_temp_iid = acc.char_target_temp.to_HAP()[HAP_REPR_IID]
    char_target_heat_cool_iid = acc.char_target_heat_cool.to_HAP()[HAP_REPR_IID]
    call_set_hvac_mode = async_mock_service(hass, DOMAIN_CLIMATE, "set_hvac_mode")
    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_heat_cool_iid,
                    HAP_REPR_VALUE: HC_HEAT_COOL_AUTO,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_temp_iid,
                    HAP_REPR_VALUE: 0,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert call_set_hvac_mode
    assert call_set_hvac_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVACMode.COOL
    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_heat_cool_iid,
                    HAP_REPR_VALUE: HC_HEAT_COOL_AUTO,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_temp_iid,
                    HAP_REPR_VALUE: 200,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert call_set_hvac_mode
    assert call_set_hvac_mode[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_hvac_mode[1].data[ATTR_HVAC_MODE] == HVACMode.HEAT


async def test_thermostat_hvac_modes_without_off(
    hass: HomeAssistant, hk_driver
) -> None:
    """Test a thermostat that has no off."""
    entity_id = "climate.test"

    hass.states.async_set(
        entity_id, HVACMode.AUTO, {ATTR_HVAC_MODES: [HVACMode.AUTO, HVACMode.HEAT]}
    )

    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()
    hap = acc.char_target_heat_cool.to_HAP()
    assert hap["valid-values"] == [1, 3]
    assert acc.char_target_heat_cool.value == 3

    acc.char_target_heat_cool.set_value(3)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 3

    acc.char_target_heat_cool.set_value(1)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1

    with pytest.raises(ValueError):
        acc.char_target_heat_cool.set_value(2)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1

    with pytest.raises(ValueError):
        acc.char_target_heat_cool.set_value(0)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1


async def test_thermostat_without_target_temp_only_range(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test a thermostat that only supports a range."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    }

    # support_auto = True
    hass.states.async_set(
        entity_id,
        HVACMode.OFF,
        base_attrs,
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_heating_thresh_temp.value == 19.0

    assert acc.char_cooling_thresh_temp.properties[PROP_MAX_VALUE] == DEFAULT_MAX_TEMP
    assert acc.char_cooling_thresh_temp.properties[PROP_MIN_VALUE] == 7.0
    assert acc.char_cooling_thresh_temp.properties[PROP_MIN_STEP] == 0.1
    assert acc.char_heating_thresh_temp.properties[PROP_MAX_VALUE] == DEFAULT_MAX_TEMP
    assert acc.char_heating_thresh_temp.properties[PROP_MIN_VALUE] == 7.0
    assert acc.char_heating_thresh_temp.properties[PROP_MIN_STEP] == 0.1

    hass.states.async_set(
        entity_id,
        HVACMode.HEAT_COOL,
        {
            **base_attrs,
            ATTR_TARGET_TEMP_HIGH: 22.0,
            ATTR_TARGET_TEMP_LOW: 20.0,
            ATTR_CURRENT_TEMPERATURE: 18.0,
            ATTR_HVAC_ACTION: HVACAction.HEATING,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_heating_thresh_temp.value == 20.0
    assert acc.char_cooling_thresh_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 1
    assert acc.char_target_heat_cool.value == 3
    assert acc.char_current_temp.value == 18.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(
        entity_id,
        HVACMode.COOL,
        {
            **base_attrs,
            ATTR_TARGET_TEMP_HIGH: 23.0,
            ATTR_TARGET_TEMP_LOW: 19.0,
            ATTR_CURRENT_TEMPERATURE: 24.0,
            ATTR_HVAC_ACTION: HVACAction.COOLING,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_heating_thresh_temp.value == 19.0
    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_current_heat_cool.value == 2
    assert acc.char_target_heat_cool.value == 2
    assert acc.char_current_temp.value == 24.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(
        entity_id,
        HVACMode.COOL,
        {
            **base_attrs,
            ATTR_TARGET_TEMP_HIGH: 23.0,
            ATTR_TARGET_TEMP_LOW: 19.0,
            ATTR_CURRENT_TEMPERATURE: 21.0,
            ATTR_HVAC_ACTION: HVACAction.IDLE,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_heating_thresh_temp.value == 19.0
    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 2
    assert acc.char_current_temp.value == 21.0
    assert acc.char_display_units.value == 0

    # Set from HomeKit
    call_set_temperature = async_mock_service(hass, DOMAIN_CLIMATE, "set_temperature")

    char_target_temp_iid = acc.char_target_temp.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_temp_iid,
                    HAP_REPR_VALUE: 17.0,
                }
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert call_set_temperature[0]
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TARGET_TEMP_LOW] == 12.0
    assert call_set_temperature[0].data[ATTR_TARGET_TEMP_HIGH] == 17.0
    assert acc.char_target_temp.value == 17.0
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "CoolingThresholdTemperature to 17.0°C"

    hass.states.async_set(
        entity_id,
        HVACMode.HEAT,
        {
            ATTR_TARGET_TEMP_HIGH: 23.0,
            ATTR_TARGET_TEMP_LOW: 19.0,
            ATTR_CURRENT_TEMPERATURE: 21.0,
            ATTR_HVAC_ACTION: HVACAction.IDLE,
            ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_heating_thresh_temp.value == 19.0
    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 1
    assert acc.char_current_temp.value == 21.0
    assert acc.char_display_units.value == 0

    # Set from HomeKit
    call_set_temperature = async_mock_service(hass, DOMAIN_CLIMATE, "set_temperature")

    char_target_temp_iid = acc.char_target_temp.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_temp_iid,
                    HAP_REPR_VALUE: 27.0,
                }
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert call_set_temperature[0]
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TARGET_TEMP_LOW] == 27.0
    assert call_set_temperature[0].data[ATTR_TARGET_TEMP_HIGH] == 32.0
    assert acc.char_target_temp.value == 27.0
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == "HeatingThresholdTemperature to 27.0°C"


async def test_water_heater(hass: HomeAssistant, hk_driver, events) -> None:
    """Test if accessory and HA are updated accordingly."""
    entity_id = "water_heater.test"

    hass.states.async_set(entity_id, HVACMode.HEAT)
    await hass.async_block_till_done()
    acc = WaterHeater(hass, hk_driver, "WaterHeater", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 9  # Thermostat

    assert acc.char_current_heat_cool.value == 1  # Heat
    assert acc.char_target_heat_cool.value == 1  # Heat
    assert acc.char_current_temp.value == 50.0
    assert acc.char_target_temp.value == 50.0
    assert acc.char_display_units.value == 0

    assert (
        acc.char_target_temp.properties[PROP_MAX_VALUE] == DEFAULT_MAX_TEMP_WATER_HEATER
    )
    assert (
        acc.char_target_temp.properties[PROP_MIN_VALUE] == DEFAULT_MIN_TEMP_WATER_HEATER
    )
    assert acc.char_target_temp.properties[PROP_MIN_STEP] == 0.1

    hass.states.async_set(
        entity_id,
        HVACMode.HEAT,
        {
            ATTR_HVAC_MODE: HVACMode.HEAT,
            ATTR_TEMPERATURE: 56.0,
            ATTR_CURRENT_TEMPERATURE: 35.0,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 56.0
    assert acc.char_current_temp.value == 35.0
    assert acc.char_target_heat_cool.value == 1
    assert acc.char_current_heat_cool.value == 1
    assert acc.char_display_units.value == 0

    hass.states.async_set(
        entity_id, HVACMode.HEAT_COOL, {ATTR_HVAC_MODE: HVACMode.HEAT_COOL}
    )
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1
    assert acc.char_current_heat_cool.value == 1

    # Set from HomeKit
    call_set_temperature = async_mock_service(
        hass, DOMAIN_WATER_HEATER, "set_temperature"
    )

    acc.char_target_temp.client_update_value(52.0)
    await hass.async_block_till_done()
    assert call_set_temperature
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TEMPERATURE] == 52.0
    assert acc.char_target_temp.value == 52.0
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == f"52.0{UnitOfTemperature.CELSIUS}"

    acc.char_target_heat_cool.client_update_value(1)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1

    with pytest.raises(ValueError):
        acc.char_target_heat_cool.set_value(3)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1


async def test_water_heater_fahrenheit(hass: HomeAssistant, hk_driver, events) -> None:
    """Test if accessory and HA are update accordingly."""
    entity_id = "water_heater.test"

    hass.states.async_set(entity_id, HVACMode.HEAT)
    await hass.async_block_till_done()
    with patch.object(
        hass.config.units, CONF_TEMPERATURE_UNIT, new=UnitOfTemperature.FAHRENHEIT
    ):
        acc = WaterHeater(hass, hk_driver, "WaterHeater", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    hass.states.async_set(entity_id, HVACMode.HEAT, {ATTR_TEMPERATURE: 131})
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 55.0
    assert acc.char_current_temp.value == 50
    assert acc.char_display_units.value == 1

    # Set from HomeKit
    call_set_temperature = async_mock_service(
        hass, DOMAIN_WATER_HEATER, "set_temperature"
    )

    acc.char_target_temp.client_update_value(60)
    await hass.async_block_till_done()
    assert call_set_temperature
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TEMPERATURE] == 140.0
    assert acc.char_target_temp.value == 60.0
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "140.0°F"


async def test_water_heater_get_temperature_range(
    hass: HomeAssistant, hk_driver
) -> None:
    """Test if temperature range is evaluated correctly."""
    entity_id = "water_heater.test"

    hass.states.async_set(entity_id, HVACMode.HEAT)
    await hass.async_block_till_done()
    acc = WaterHeater(hass, hk_driver, "WaterHeater", entity_id, 2, None)

    hass.states.async_set(
        entity_id, HVACMode.HEAT, {ATTR_MIN_TEMP: 20, ATTR_MAX_TEMP: 25}
    )
    state = hass.states.get(entity_id)
    assert state
    await hass.async_block_till_done()
    assert acc.get_temperature_range(state) == (20, 25)

    acc._unit = UnitOfTemperature.FAHRENHEIT
    hass.states.async_set(
        entity_id, HVACMode.OFF, {ATTR_MIN_TEMP: 60, ATTR_MAX_TEMP: 70}
    )
    state = hass.states.get(entity_id)
    assert state
    await hass.async_block_till_done()
    assert acc.get_temperature_range(state) == (15.5, 21.0)


async def test_water_heater_restore(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, hk_driver, events
) -> None:
    """Test setting up an entity from state in the event registry."""
    hass.state = CoreState.not_running

    entity_registry.async_get_or_create(
        "water_heater", "generic", "1234", suggested_object_id="simple"
    )
    entity_registry.async_get_or_create(
        "water_heater",
        "generic",
        "9012",
        suggested_object_id="all_info_set",
        capabilities={ATTR_MIN_TEMP: 60, ATTR_MAX_TEMP: 70},
        supported_features=0,
        original_device_class="mock-device-class",
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START, {})
    await hass.async_block_till_done()

    entity_id = "water_heater.simple"
    hass.states.async_set(entity_id, "off")
    state = hass.states.get(entity_id)
    assert state

    acc = Thermostat(hass, hk_driver, "WaterHeater", entity_id, 2, None)
    assert acc.category == 9
    assert acc.get_temperature_range(state) == (7, 35)
    assert set(acc.char_current_heat_cool.properties["ValidValues"].keys()) == {
        "Cool",
        "Heat",
        "Off",
    }

    entity_id = "water_heater.all_info_set"
    state = hass.states.get(entity_id)
    assert state

    acc = WaterHeater(hass, hk_driver, "WaterHeater", entity_id, 3, None)
    assert acc.category == 9
    assert acc.get_temperature_range(state) == (60.0, 70.0)
    assert set(acc.char_current_heat_cool.properties["ValidValues"].keys()) == {
        "Cool",
        "Heat",
        "Off",
    }


async def test_thermostat_with_no_modes_when_we_first_see(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test if a thermostat that is not ready when we first see it."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
        ATTR_HVAC_MODES: [],
    }

    # support_auto = True
    hass.states.async_set(
        entity_id,
        HVACMode.OFF,
        base_attrs,
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_heating_thresh_temp.value == 19.0

    assert acc.char_cooling_thresh_temp.properties[PROP_MAX_VALUE] == DEFAULT_MAX_TEMP
    assert acc.char_cooling_thresh_temp.properties[PROP_MIN_VALUE] == 7.0
    assert acc.char_cooling_thresh_temp.properties[PROP_MIN_STEP] == 0.1
    assert acc.char_heating_thresh_temp.properties[PROP_MAX_VALUE] == DEFAULT_MAX_TEMP
    assert acc.char_heating_thresh_temp.properties[PROP_MIN_VALUE] == 7.0
    assert acc.char_heating_thresh_temp.properties[PROP_MIN_STEP] == 0.1

    assert acc.char_target_heat_cool.value == 0

    # Verify reload on modes changed out from under us
    with patch.object(acc, "async_reload") as mock_reload:
        hass.states.async_set(
            entity_id,
            HVACMode.HEAT_COOL,
            {
                **base_attrs,
                ATTR_TARGET_TEMP_HIGH: 22.0,
                ATTR_TARGET_TEMP_LOW: 20.0,
                ATTR_CURRENT_TEMPERATURE: 18.0,
                ATTR_HVAC_ACTION: HVACAction.HEATING,
                ATTR_HVAC_MODES: [HVACMode.HEAT_COOL, HVACMode.OFF, HVACMode.AUTO],
            },
        )
        await hass.async_block_till_done()
        assert mock_reload.called


async def test_thermostat_with_no_off_after_recheck(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test if a thermostat that is not ready when we first see it that actually does not have off."""
    entity_id = "climate.test"

    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
        ATTR_HVAC_MODES: [],
    }
    # support_auto = True
    hass.states.async_set(
        entity_id,
        HVACMode.COOL,
        base_attrs,
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_heating_thresh_temp.value == 19.0

    assert acc.char_cooling_thresh_temp.properties[PROP_MAX_VALUE] == DEFAULT_MAX_TEMP
    assert acc.char_cooling_thresh_temp.properties[PROP_MIN_VALUE] == 7.0
    assert acc.char_cooling_thresh_temp.properties[PROP_MIN_STEP] == 0.1
    assert acc.char_heating_thresh_temp.properties[PROP_MAX_VALUE] == DEFAULT_MAX_TEMP
    assert acc.char_heating_thresh_temp.properties[PROP_MIN_VALUE] == 7.0
    assert acc.char_heating_thresh_temp.properties[PROP_MIN_STEP] == 0.1

    assert acc.char_target_heat_cool.value == 2

    # Verify reload when modes change out from under us
    with patch.object(acc, "async_reload") as mock_reload:
        hass.states.async_set(
            entity_id,
            HVACMode.HEAT_COOL,
            {
                **base_attrs,
                ATTR_TARGET_TEMP_HIGH: 22.0,
                ATTR_TARGET_TEMP_LOW: 20.0,
                ATTR_CURRENT_TEMPERATURE: 18.0,
                ATTR_HVAC_ACTION: HVACAction.HEATING,
                ATTR_HVAC_MODES: [HVACMode.HEAT_COOL, HVACMode.AUTO],
            },
        )
        await hass.async_block_till_done()
        assert mock_reload.called


async def test_thermostat_with_temp_clamps(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test that tempatures are clamped to valid values to prevent homekit crash."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
        ATTR_HVAC_MODES: [HVACMode.HEAT_COOL, HVACMode.AUTO],
        ATTR_MAX_TEMP: 50,
        ATTR_MIN_TEMP: 100,
    }
    hass.states.async_set(
        entity_id,
        HVACMode.COOL,
        base_attrs,
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_cooling_thresh_temp.value == 100
    assert acc.char_heating_thresh_temp.value == 100

    assert acc.char_cooling_thresh_temp.properties[PROP_MAX_VALUE] == 100
    assert acc.char_cooling_thresh_temp.properties[PROP_MIN_VALUE] == 100
    assert acc.char_cooling_thresh_temp.properties[PROP_MIN_STEP] == 0.1
    assert acc.char_heating_thresh_temp.properties[PROP_MAX_VALUE] == 100
    assert acc.char_heating_thresh_temp.properties[PROP_MIN_VALUE] == 100
    assert acc.char_heating_thresh_temp.properties[PROP_MIN_STEP] == 0.1

    assert acc.char_target_heat_cool.value == 3

    hass.states.async_set(
        entity_id,
        HVACMode.HEAT_COOL,
        {
            **base_attrs,
            ATTR_TARGET_TEMP_HIGH: 822.0,
            ATTR_TARGET_TEMP_LOW: 20.0,
            ATTR_CURRENT_TEMPERATURE: 9918.0,
            ATTR_HVAC_ACTION: HVACAction.HEATING,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_heating_thresh_temp.value == 100.0
    assert acc.char_cooling_thresh_temp.value == 100.0
    assert acc.char_current_heat_cool.value == 1
    assert acc.char_target_heat_cool.value == 3
    assert acc.char_current_temp.value == 1000
    assert acc.char_display_units.value == 0


async def test_thermostat_with_fan_modes_with_auto(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test a thermostate with fan modes with an auto fan mode."""
    entity_id = "climate.test"
    hass.states.async_set(
        entity_id,
        HVACMode.OFF,
        {
            ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE,
            ATTR_FAN_MODES: [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH],
            ATTR_SWING_MODES: [SWING_BOTH, SWING_OFF, SWING_HORIZONTAL],
            ATTR_HVAC_ACTION: HVACAction.IDLE,
            ATTR_FAN_MODE: FAN_AUTO,
            ATTR_SWING_MODE: SWING_BOTH,
            ATTR_HVAC_MODES: [
                HVACMode.HEAT,
                HVACMode.HEAT_COOL,
                HVACMode.FAN_ONLY,
                HVACMode.COOL,
                HVACMode.OFF,
                HVACMode.AUTO,
            ],
        },
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_heating_thresh_temp.value == 19.0
    assert acc.ordered_fan_speeds == [FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    assert CHAR_ROTATION_SPEED in acc.fan_chars
    assert CHAR_TARGET_FAN_STATE in acc.fan_chars
    assert CHAR_SWING_MODE in acc.fan_chars
    assert CHAR_CURRENT_FAN_STATE in acc.fan_chars
    assert acc.char_speed.value == 100

    hass.states.async_set(
        entity_id,
        HVACMode.OFF,
        {
            ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE,
            ATTR_FAN_MODES: [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH],
            ATTR_SWING_MODES: [SWING_BOTH, SWING_OFF, SWING_HORIZONTAL],
            ATTR_HVAC_ACTION: HVACAction.IDLE,
            ATTR_FAN_MODE: FAN_LOW,
            ATTR_SWING_MODE: SWING_BOTH,
            ATTR_HVAC_MODES: [
                HVACMode.HEAT,
                HVACMode.HEAT_COOL,
                HVACMode.FAN_ONLY,
                HVACMode.COOL,
                HVACMode.OFF,
                HVACMode.AUTO,
            ],
        },
    )
    await hass.async_block_till_done()
    assert acc.char_speed.value == pytest.approx(100 / 3)

    call_set_swing_mode = async_mock_service(
        hass, DOMAIN_CLIMATE, SERVICE_SET_SWING_MODE
    )
    char_swing_iid = acc.char_swing.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_swing_iid,
                    HAP_REPR_VALUE: 0,
                }
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert len(call_set_swing_mode) == 1
    assert call_set_swing_mode[-1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_swing_mode[-1].data[ATTR_SWING_MODE] == SWING_OFF

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_swing_iid,
                    HAP_REPR_VALUE: 1,
                }
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert len(call_set_swing_mode) == 2
    assert call_set_swing_mode[-1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_swing_mode[-1].data[ATTR_SWING_MODE] == SWING_BOTH

    call_set_fan_mode = async_mock_service(hass, DOMAIN_CLIMATE, SERVICE_SET_FAN_MODE)
    char_rotation_speed_iid = acc.char_speed.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_rotation_speed_iid,
                    HAP_REPR_VALUE: 100,
                }
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert len(call_set_fan_mode) == 1
    assert call_set_fan_mode[-1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_fan_mode[-1].data[ATTR_FAN_MODE] == FAN_HIGH

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_rotation_speed_iid,
                    HAP_REPR_VALUE: 100 / 3,
                }
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert len(call_set_fan_mode) == 2
    assert call_set_fan_mode[-1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_fan_mode[-1].data[ATTR_FAN_MODE] == FAN_LOW

    char_active_iid = acc.char_active.to_HAP()[HAP_REPR_IID]
    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_active_iid,
                    HAP_REPR_VALUE: 0,
                }
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert acc.char_active.value == 1

    char_target_fan_state_iid = acc.char_target_fan_state.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_fan_state_iid,
                    HAP_REPR_VALUE: 1,
                }
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert len(call_set_fan_mode) == 3
    assert call_set_fan_mode[-1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_fan_mode[-1].data[ATTR_FAN_MODE] == FAN_AUTO

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_fan_state_iid,
                    HAP_REPR_VALUE: 0,
                }
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert len(call_set_fan_mode) == 4
    assert call_set_fan_mode[-1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_fan_mode[-1].data[ATTR_FAN_MODE] == FAN_MEDIUM


async def test_thermostat_with_fan_modes_with_off(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test a thermostate with fan modes that can turn off."""
    entity_id = "climate.test"
    hass.states.async_set(
        entity_id,
        HVACMode.COOL,
        {
            ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE,
            ATTR_FAN_MODES: [FAN_ON, FAN_OFF],
            ATTR_SWING_MODES: [SWING_BOTH, SWING_OFF, SWING_HORIZONTAL],
            ATTR_HVAC_ACTION: HVACAction.IDLE,
            ATTR_FAN_MODE: FAN_ON,
            ATTR_SWING_MODE: SWING_BOTH,
            ATTR_HVAC_MODES: [
                HVACMode.HEAT,
                HVACMode.HEAT_COOL,
                HVACMode.FAN_ONLY,
                HVACMode.COOL,
                HVACMode.OFF,
                HVACMode.AUTO,
            ],
        },
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_heating_thresh_temp.value == 19.0
    assert acc.ordered_fan_speeds == []
    assert CHAR_ROTATION_SPEED not in acc.fan_chars
    assert CHAR_TARGET_FAN_STATE not in acc.fan_chars
    assert CHAR_SWING_MODE in acc.fan_chars
    assert CHAR_CURRENT_FAN_STATE in acc.fan_chars
    assert acc.char_active.value == 1

    hass.states.async_set(
        entity_id,
        HVACMode.COOL,
        {
            ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE,
            ATTR_FAN_MODES: [FAN_ON, FAN_OFF],
            ATTR_SWING_MODES: [SWING_BOTH, SWING_OFF, SWING_HORIZONTAL],
            ATTR_HVAC_ACTION: HVACAction.IDLE,
            ATTR_FAN_MODE: FAN_OFF,
            ATTR_SWING_MODE: SWING_BOTH,
            ATTR_HVAC_MODES: [
                HVACMode.HEAT,
                HVACMode.HEAT_COOL,
                HVACMode.FAN_ONLY,
                HVACMode.COOL,
                HVACMode.OFF,
                HVACMode.AUTO,
            ],
        },
    )
    await hass.async_block_till_done()
    assert acc.char_active.value == 0

    call_set_fan_mode = async_mock_service(hass, DOMAIN_CLIMATE, SERVICE_SET_FAN_MODE)
    char_active_iid = acc.char_active.to_HAP()[HAP_REPR_IID]
    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_active_iid,
                    HAP_REPR_VALUE: 1,
                }
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert len(call_set_fan_mode) == 1
    assert call_set_fan_mode[-1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_fan_mode[-1].data[ATTR_FAN_MODE] == FAN_ON

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_active_iid,
                    HAP_REPR_VALUE: 0,
                }
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert len(call_set_fan_mode) == 2
    assert call_set_fan_mode[-1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_fan_mode[-1].data[ATTR_FAN_MODE] == FAN_OFF


async def test_thermostat_with_fan_modes_set_to_none(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test a thermostate with fan modes set to None."""
    entity_id = "climate.test"
    hass.states.async_set(
        entity_id,
        HVACMode.OFF,
        {
            ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE,
            ATTR_FAN_MODES: None,
            ATTR_SWING_MODES: [SWING_BOTH, SWING_OFF, SWING_HORIZONTAL],
            ATTR_HVAC_ACTION: HVACAction.IDLE,
            ATTR_FAN_MODE: FAN_AUTO,
            ATTR_SWING_MODE: SWING_BOTH,
            ATTR_HVAC_MODES: [
                HVACMode.HEAT,
                HVACMode.HEAT_COOL,
                HVACMode.FAN_ONLY,
                HVACMode.COOL,
                HVACMode.OFF,
                HVACMode.AUTO,
            ],
        },
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_heating_thresh_temp.value == 19.0
    assert acc.ordered_fan_speeds == []
    assert CHAR_ROTATION_SPEED not in acc.fan_chars
    assert CHAR_TARGET_FAN_STATE not in acc.fan_chars
    assert CHAR_SWING_MODE in acc.fan_chars
    assert CHAR_CURRENT_FAN_STATE in acc.fan_chars


async def test_thermostat_with_fan_modes_set_to_none_not_supported(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test a thermostate with fan modes set to None and supported feature missing."""
    entity_id = "climate.test"
    hass.states.async_set(
        entity_id,
        HVACMode.OFF,
        {
            ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            | ClimateEntityFeature.SWING_MODE,
            ATTR_FAN_MODES: None,
            ATTR_SWING_MODES: [SWING_BOTH, SWING_OFF, SWING_HORIZONTAL],
            ATTR_HVAC_ACTION: HVACAction.IDLE,
            ATTR_FAN_MODE: FAN_AUTO,
            ATTR_SWING_MODE: SWING_BOTH,
            ATTR_HVAC_MODES: [
                HVACMode.HEAT,
                HVACMode.HEAT_COOL,
                HVACMode.FAN_ONLY,
                HVACMode.COOL,
                HVACMode.OFF,
                HVACMode.AUTO,
            ],
        },
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_cooling_thresh_temp.value == 23.0
    assert acc.char_heating_thresh_temp.value == 19.0
    assert acc.ordered_fan_speeds == []
    assert CHAR_ROTATION_SPEED not in acc.fan_chars
    assert CHAR_TARGET_FAN_STATE not in acc.fan_chars
    assert CHAR_SWING_MODE in acc.fan_chars
    assert CHAR_CURRENT_FAN_STATE in acc.fan_chars


async def test_thermostat_with_supported_features_target_temp_but_fan_mode_set(
    hass: HomeAssistant, hk_driver, events
) -> None:
    """Test a thermostate with fan mode and supported feature missing."""
    entity_id = "climate.test"
    hass.states.async_set(
        entity_id,
        HVACMode.OFF,
        {
            ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
            ATTR_MIN_TEMP: 44.6,
            ATTR_MAX_TEMP: 95,
            ATTR_PRESET_MODES: ["home", "away"],
            ATTR_TEMPERATURE: 67,
            ATTR_TARGET_TEMP_HIGH: None,
            ATTR_TARGET_TEMP_LOW: None,
            ATTR_FAN_MODE: FAN_AUTO,
            ATTR_FAN_MODES: None,
            ATTR_HVAC_ACTION: HVACAction.IDLE,
            ATTR_PRESET_MODE: "home",
            ATTR_FRIENDLY_NAME: "Rec Room",
            ATTR_HVAC_MODES: [
                HVACMode.OFF,
                HVACMode.HEAT,
            ],
        },
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.ordered_fan_speeds == []
    assert not acc.fan_chars
