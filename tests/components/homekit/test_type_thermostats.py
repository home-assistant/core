"""Test different accessory types: Thermostats."""
from unittest.mock import patch

from pyhap.const import HAP_REPR_AID, HAP_REPR_CHARS, HAP_REPR_IID, HAP_REPR_VALUE
import pytest

from homeassistant.components.climate.const import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_STEP,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_DRY,
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_HUMIDITY,
    DOMAIN as DOMAIN_CLIMATE,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.components.homekit.const import (
    ATTR_VALUE,
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
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    CONF_TEMPERATURE_UNIT,
    EVENT_HOMEASSISTANT_START,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import CoreState
from homeassistant.helpers import entity_registry

from tests.common import async_mock_service


async def test_thermostat(hass, hk_driver, events):
    """Test if accessory and HA are updated accordingly."""
    entity_id = "climate.test"

    hass.states.async_set(
        entity_id,
        HVAC_MODE_OFF,
        {
            ATTR_SUPPORTED_FEATURES: SUPPORT_TARGET_TEMPERATURE,
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT,
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_FAN_ONLY,
                HVAC_MODE_COOL,
                HVAC_MODE_OFF,
                HVAC_MODE_AUTO,
            ],
        },
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()

    assert acc.aid == 1
    assert acc.category == 9  # Thermostat

    assert acc.get_temperature_range() == (7.0, 35.0)
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
        HVAC_MODE_HEAT,
        {
            ATTR_TEMPERATURE: 22.2,
            ATTR_CURRENT_TEMPERATURE: 17.8,
            ATTR_HVAC_ACTION: CURRENT_HVAC_HEAT,
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT,
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_FAN_ONLY,
                HVAC_MODE_COOL,
                HVAC_MODE_OFF,
                HVAC_MODE_AUTO,
            ],
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
        HVAC_MODE_HEAT,
        {
            ATTR_TEMPERATURE: 22.0,
            ATTR_CURRENT_TEMPERATURE: 23.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_IDLE,
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT,
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_FAN_ONLY,
                HVAC_MODE_COOL,
                HVAC_MODE_OFF,
                HVAC_MODE_AUTO,
            ],
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
        HVAC_MODE_FAN_ONLY,
        {
            ATTR_TEMPERATURE: 20.0,
            ATTR_CURRENT_TEMPERATURE: 25.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_COOL,
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT,
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_FAN_ONLY,
                HVAC_MODE_COOL,
                HVAC_MODE_OFF,
                HVAC_MODE_AUTO,
            ],
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
        HVAC_MODE_COOL,
        {
            ATTR_TEMPERATURE: 20.0,
            ATTR_CURRENT_TEMPERATURE: 19.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_IDLE,
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
        HVAC_MODE_OFF,
        {ATTR_TEMPERATURE: 22.0, ATTR_CURRENT_TEMPERATURE: 18.0},
    )
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 0
    assert acc.char_current_temp.value == 18.0
    assert acc.char_display_units.value == 0

    hass.states.async_set(
        entity_id,
        HVAC_MODE_AUTO,
        {
            ATTR_TEMPERATURE: 22.0,
            ATTR_CURRENT_TEMPERATURE: 18.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_HEAT,
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT,
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_FAN_ONLY,
                HVAC_MODE_COOL,
                HVAC_MODE_OFF,
                HVAC_MODE_AUTO,
            ],
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
        HVAC_MODE_HEAT_COOL,
        {
            ATTR_TEMPERATURE: 22.0,
            ATTR_CURRENT_TEMPERATURE: 25.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_COOL,
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT,
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_FAN_ONLY,
                HVAC_MODE_COOL,
                HVAC_MODE_OFF,
                HVAC_MODE_AUTO,
            ],
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
        HVAC_MODE_AUTO,
        {
            ATTR_TEMPERATURE: 22.0,
            ATTR_CURRENT_TEMPERATURE: 22.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_IDLE,
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT,
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_FAN_ONLY,
                HVAC_MODE_COOL,
                HVAC_MODE_OFF,
                HVAC_MODE_AUTO,
            ],
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
        HVAC_MODE_FAN_ONLY,
        {
            ATTR_TEMPERATURE: 22.0,
            ATTR_CURRENT_TEMPERATURE: 22.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_FAN,
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT,
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_FAN_ONLY,
                HVAC_MODE_COOL,
                HVAC_MODE_OFF,
                HVAC_MODE_AUTO,
            ],
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
        HVAC_MODE_DRY,
        {
            ATTR_SUPPORTED_FEATURES: SUPPORT_TARGET_TEMPERATURE,
            ATTR_TEMPERATURE: 22.0,
            ATTR_CURRENT_TEMPERATURE: 22.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_DRY,
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
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVAC_MODE_HEAT
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
    assert call_set_hvac_mode[1].data[ATTR_HVAC_MODE] == HVAC_MODE_HEAT_COOL
    assert acc.char_target_heat_cool.value == 3
    assert len(events) == 3
    assert events[-1].data[ATTR_VALUE] == "TargetHeatingCoolingState to 3"


async def test_thermostat_auto(hass, hk_driver, events):
    """Test if accessory and HA are updated accordingly."""
    entity_id = "climate.test"

    # support_auto = True
    hass.states.async_set(
        entity_id,
        HVAC_MODE_OFF,
        {
            ATTR_SUPPORTED_FEATURES: SUPPORT_TARGET_TEMPERATURE
            | SUPPORT_TARGET_TEMPERATURE_RANGE,
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT,
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_FAN_ONLY,
                HVAC_MODE_COOL,
                HVAC_MODE_OFF,
                HVAC_MODE_AUTO,
            ],
        },
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
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
        HVAC_MODE_HEAT_COOL,
        {
            ATTR_TARGET_TEMP_HIGH: 22.0,
            ATTR_TARGET_TEMP_LOW: 20.0,
            ATTR_CURRENT_TEMPERATURE: 18.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_HEAT,
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT,
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_FAN_ONLY,
                HVAC_MODE_COOL,
                HVAC_MODE_OFF,
                HVAC_MODE_AUTO,
            ],
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
        HVAC_MODE_COOL,
        {
            ATTR_TARGET_TEMP_HIGH: 23.0,
            ATTR_TARGET_TEMP_LOW: 19.0,
            ATTR_CURRENT_TEMPERATURE: 24.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_COOL,
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT,
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_FAN_ONLY,
                HVAC_MODE_COOL,
                HVAC_MODE_OFF,
                HVAC_MODE_AUTO,
            ],
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
        HVAC_MODE_AUTO,
        {
            ATTR_TARGET_TEMP_HIGH: 23.0,
            ATTR_TARGET_TEMP_LOW: 19.0,
            ATTR_CURRENT_TEMPERATURE: 21.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_IDLE,
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT,
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_FAN_ONLY,
                HVAC_MODE_COOL,
                HVAC_MODE_OFF,
                HVAC_MODE_AUTO,
            ],
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


async def test_thermostat_humidity(hass, hk_driver, events):
    """Test if accessory and HA are updated accordingly with humidity."""
    entity_id = "climate.test"

    # support_auto = True
    hass.states.async_set(entity_id, HVAC_MODE_OFF, {ATTR_SUPPORTED_FEATURES: 4})
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()

    assert acc.char_target_humidity.value == 50
    assert acc.char_current_humidity.value == 50

    assert acc.char_target_humidity.properties[PROP_MIN_VALUE] == DEFAULT_MIN_HUMIDITY

    hass.states.async_set(
        entity_id, HVAC_MODE_HEAT_COOL, {ATTR_HUMIDITY: 65, ATTR_CURRENT_HUMIDITY: 40}
    )
    await hass.async_block_till_done()
    assert acc.char_current_humidity.value == 40
    assert acc.char_target_humidity.value == 65

    hass.states.async_set(
        entity_id, HVAC_MODE_COOL, {ATTR_HUMIDITY: 35, ATTR_CURRENT_HUMIDITY: 70}
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


async def test_thermostat_power_state(hass, hk_driver, events):
    """Test if accessory and HA are updated accordingly."""
    entity_id = "climate.test"

    # SUPPORT_ON_OFF = True
    hass.states.async_set(
        entity_id,
        HVAC_MODE_HEAT,
        {
            ATTR_SUPPORTED_FEATURES: 4096,
            ATTR_TEMPERATURE: 23.0,
            ATTR_CURRENT_TEMPERATURE: 18.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_HEAT,
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_COOL,
                HVAC_MODE_AUTO,
                HVAC_MODE_HEAT,
                HVAC_MODE_OFF,
            ],
        },
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()

    assert acc.char_current_heat_cool.value == 1
    assert acc.char_target_heat_cool.value == 1

    hass.states.async_set(
        entity_id,
        HVAC_MODE_OFF,
        {
            ATTR_TEMPERATURE: 23.0,
            ATTR_CURRENT_TEMPERATURE: 18.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_IDLE,
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_COOL,
                HVAC_MODE_AUTO,
                HVAC_MODE_HEAT,
                HVAC_MODE_OFF,
            ],
        },
    )
    await hass.async_block_till_done()
    assert acc.char_current_heat_cool.value == 0
    assert acc.char_target_heat_cool.value == 0

    hass.states.async_set(
        entity_id,
        HVAC_MODE_OFF,
        {
            ATTR_TEMPERATURE: 23.0,
            ATTR_CURRENT_TEMPERATURE: 18.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_IDLE,
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_COOL,
                HVAC_MODE_AUTO,
                HVAC_MODE_HEAT,
                HVAC_MODE_OFF,
            ],
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
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVAC_MODE_HEAT
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
    assert call_set_hvac_mode[1].data[ATTR_HVAC_MODE] == HVAC_MODE_COOL
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == "TargetHeatingCoolingState to 2"
    assert acc.char_target_heat_cool.value == 2


async def test_thermostat_fahrenheit(hass, hk_driver, events):
    """Test if accessory and HA are updated accordingly."""
    entity_id = "climate.test"

    # support_ = True
    hass.states.async_set(
        entity_id,
        HVAC_MODE_OFF,
        {
            ATTR_SUPPORTED_FEATURES: SUPPORT_TARGET_TEMPERATURE
            | SUPPORT_TARGET_TEMPERATURE_RANGE
        },
    )
    await hass.async_block_till_done()
    with patch.object(hass.config.units, CONF_TEMPERATURE_UNIT, new=TEMP_FAHRENHEIT):
        acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)
    await acc.run_handler()
    await hass.async_block_till_done()

    hass.states.async_set(
        entity_id,
        HVAC_MODE_HEAT_COOL,
        {
            ATTR_TARGET_TEMP_HIGH: 75.2,
            ATTR_TARGET_TEMP_LOW: 68.1,
            ATTR_TEMPERATURE: 71.6,
            ATTR_CURRENT_TEMPERATURE: 73.4,
            ATTR_SUPPORTED_FEATURES: SUPPORT_TARGET_TEMPERATURE
            | SUPPORT_TARGET_TEMPERATURE_RANGE,
        },
    )
    await hass.async_block_till_done()
    assert acc.get_temperature_range() == (7.0, 35.0)
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


async def test_thermostat_get_temperature_range(hass, hk_driver):
    """Test if temperature range is evaluated correctly."""
    entity_id = "climate.test"

    hass.states.async_set(entity_id, HVAC_MODE_OFF)
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 2, None)

    hass.states.async_set(
        entity_id, HVAC_MODE_OFF, {ATTR_MIN_TEMP: 20, ATTR_MAX_TEMP: 25}
    )
    await hass.async_block_till_done()
    assert acc.get_temperature_range() == (20, 25)

    acc._unit = TEMP_FAHRENHEIT
    hass.states.async_set(
        entity_id, HVAC_MODE_OFF, {ATTR_MIN_TEMP: 60, ATTR_MAX_TEMP: 70}
    )
    await hass.async_block_till_done()
    assert acc.get_temperature_range() == (15.5, 21.0)


async def test_thermostat_temperature_step_whole(hass, hk_driver):
    """Test climate device with single digit precision."""
    entity_id = "climate.test"

    hass.states.async_set(entity_id, HVAC_MODE_OFF, {ATTR_TARGET_TEMP_STEP: 1})
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()

    assert acc.char_target_temp.properties[PROP_MIN_STEP] == 0.1


async def test_thermostat_restore(hass, hk_driver, events):
    """Test setting up an entity from state in the event registry."""
    hass.state = CoreState.not_running

    registry = await entity_registry.async_get_registry(hass)

    registry.async_get_or_create(
        "climate", "generic", "1234", suggested_object_id="simple"
    )
    registry.async_get_or_create(
        "climate",
        "generic",
        "9012",
        suggested_object_id="all_info_set",
        capabilities={
            ATTR_MIN_TEMP: 60,
            ATTR_MAX_TEMP: 70,
            ATTR_HVAC_MODES: [HVAC_MODE_HEAT_COOL, HVAC_MODE_OFF],
        },
        supported_features=0,
        device_class="mock-device-class",
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START, {})
    await hass.async_block_till_done()

    acc = Thermostat(hass, hk_driver, "Climate", "climate.simple", 2, None)
    assert acc.category == 9
    assert acc.get_temperature_range() == (7, 35)
    assert set(acc.char_target_heat_cool.properties["ValidValues"].keys()) == {
        "cool",
        "heat",
        "heat_cool",
        "off",
    }

    acc = Thermostat(hass, hk_driver, "Climate", "climate.all_info_set", 2, None)
    assert acc.category == 9
    assert acc.get_temperature_range() == (60.0, 70.0)
    assert set(acc.char_target_heat_cool.properties["ValidValues"].keys()) == {
        "heat_cool",
        "off",
    }


async def test_thermostat_hvac_modes(hass, hk_driver):
    """Test if unsupported HVAC modes are deactivated in HomeKit."""
    entity_id = "climate.test"

    hass.states.async_set(
        entity_id, HVAC_MODE_OFF, {ATTR_HVAC_MODES: [HVAC_MODE_HEAT, HVAC_MODE_OFF]}
    )

    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()
    hap = acc.char_target_heat_cool.to_HAP()
    assert hap["valid-values"] == [0, 1]
    assert acc.char_target_heat_cool.value == 0

    with pytest.raises(ValueError):
        await hass.async_add_executor_job(acc.char_target_heat_cool.set_value, 3)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 0

    await hass.async_add_executor_job(acc.char_target_heat_cool.set_value, 1)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1

    with pytest.raises(ValueError):
        await hass.async_add_executor_job(acc.char_target_heat_cool.set_value, 2)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1


async def test_thermostat_hvac_modes_with_auto_heat_cool(hass, hk_driver):
    """Test we get heat cool over auto."""
    entity_id = "climate.test"

    hass.states.async_set(
        entity_id,
        HVAC_MODE_OFF,
        {
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_AUTO,
                HVAC_MODE_HEAT,
                HVAC_MODE_OFF,
            ]
        },
    )
    call_set_hvac_mode = async_mock_service(hass, DOMAIN_CLIMATE, "set_hvac_mode")
    await hass.async_block_till_done()

    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()
    hap = acc.char_target_heat_cool.to_HAP()
    assert hap["valid-values"] == [0, 1, 3]
    assert acc.char_target_heat_cool.value == 0

    await hass.async_add_executor_job(acc.char_target_heat_cool.set_value, 3)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 3

    await hass.async_add_executor_job(acc.char_target_heat_cool.set_value, 1)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1

    with pytest.raises(ValueError):
        await hass.async_add_executor_job(acc.char_target_heat_cool.set_value, 2)
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
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVAC_MODE_HEAT_COOL
    assert acc.char_target_heat_cool.value == 3


async def test_thermostat_hvac_modes_with_auto_no_heat_cool(hass, hk_driver):
    """Test we get auto when there is no heat cool."""
    entity_id = "climate.test"

    hass.states.async_set(
        entity_id,
        HVAC_MODE_HEAT,
        {ATTR_HVAC_MODES: [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF]},
    )
    call_set_hvac_mode = async_mock_service(hass, DOMAIN_CLIMATE, "set_hvac_mode")
    await hass.async_block_till_done()

    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()
    hap = acc.char_target_heat_cool.to_HAP()
    assert hap["valid-values"] == [0, 1, 3]
    assert acc.char_target_heat_cool.value == 1

    await hass.async_add_executor_job(acc.char_target_heat_cool.set_value, 3)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 3

    await hass.async_add_executor_job(acc.char_target_heat_cool.set_value, 1)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1

    with pytest.raises(ValueError):
        await hass.async_add_executor_job(acc.char_target_heat_cool.set_value, 2)
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
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVAC_MODE_AUTO
    assert acc.char_target_heat_cool.value == 3


async def test_thermostat_hvac_modes_with_auto_only(hass, hk_driver):
    """Test if unsupported HVAC modes are deactivated in HomeKit."""
    entity_id = "climate.test"

    hass.states.async_set(
        entity_id, HVAC_MODE_AUTO, {ATTR_HVAC_MODES: [HVAC_MODE_AUTO, HVAC_MODE_OFF]}
    )

    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()
    hap = acc.char_target_heat_cool.to_HAP()
    assert hap["valid-values"] == [0, 3]
    assert acc.char_target_heat_cool.value == 3

    await hass.async_add_executor_job(acc.char_target_heat_cool.set_value, 3)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 3

    with pytest.raises(ValueError):
        await hass.async_add_executor_job(acc.char_target_heat_cool.set_value, 1)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 3

    with pytest.raises(ValueError):
        await hass.async_add_executor_job(acc.char_target_heat_cool.set_value, 2)
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
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVAC_MODE_AUTO


async def test_thermostat_hvac_modes_with_heat_only(hass, hk_driver):
    """Test if unsupported HVAC modes are deactivated in HomeKit and siri calls get converted to heat."""
    entity_id = "climate.test"

    hass.states.async_set(
        entity_id, HVAC_MODE_HEAT, {ATTR_HVAC_MODES: [HVAC_MODE_HEAT, HVAC_MODE_OFF]}
    )

    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()
    hap = acc.char_target_heat_cool.to_HAP()
    assert hap["valid-values"] == [HC_HEAT_COOL_OFF, HC_HEAT_COOL_HEAT]
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_HEAT

    await hass.async_add_executor_job(
        acc.char_target_heat_cool.set_value, HC_HEAT_COOL_HEAT
    )
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_HEAT

    with pytest.raises(ValueError):
        await hass.async_add_executor_job(
            acc.char_target_heat_cool.set_value, HC_HEAT_COOL_COOL
        )
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_HEAT

    with pytest.raises(ValueError):
        await hass.async_add_executor_job(
            acc.char_target_heat_cool.set_value, HC_HEAT_COOL_AUTO
        )
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
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVAC_MODE_HEAT


async def test_thermostat_hvac_modes_with_cool_only(hass, hk_driver):
    """Test if unsupported HVAC modes are deactivated in HomeKit and siri calls get converted to cool."""
    entity_id = "climate.test"

    hass.states.async_set(
        entity_id, HVAC_MODE_COOL, {ATTR_HVAC_MODES: [HVAC_MODE_COOL, HVAC_MODE_OFF]}
    )

    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()
    hap = acc.char_target_heat_cool.to_HAP()
    assert hap["valid-values"] == [HC_HEAT_COOL_OFF, HC_HEAT_COOL_COOL]
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_COOL

    await hass.async_add_executor_job(
        acc.char_target_heat_cool.set_value, HC_HEAT_COOL_COOL
    )
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_COOL

    with pytest.raises(ValueError):
        await hass.async_add_executor_job(
            acc.char_target_heat_cool.set_value, HC_HEAT_COOL_AUTO
        )
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_COOL

    with pytest.raises(ValueError):
        await hass.async_add_executor_job(
            acc.char_target_heat_cool.set_value, HC_HEAT_COOL_HEAT
        )
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
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVAC_MODE_COOL


async def test_thermostat_hvac_modes_with_heat_cool_only(hass, hk_driver):
    """Test if unsupported HVAC modes are deactivated in HomeKit and siri calls get converted to heat or cool."""
    entity_id = "climate.test"

    hass.states.async_set(
        entity_id,
        HVAC_MODE_COOL,
        {
            ATTR_CURRENT_TEMPERATURE: 30,
            ATTR_HVAC_MODES: [HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_OFF],
        },
    )

    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()
    hap = acc.char_target_heat_cool.to_HAP()
    assert hap["valid-values"] == [
        HC_HEAT_COOL_OFF,
        HC_HEAT_COOL_HEAT,
        HC_HEAT_COOL_COOL,
    ]
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_COOL

    await hass.async_add_executor_job(
        acc.char_target_heat_cool.set_value, HC_HEAT_COOL_COOL
    )
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_COOL

    with pytest.raises(ValueError):
        await hass.async_add_executor_job(
            acc.char_target_heat_cool.set_value, HC_HEAT_COOL_AUTO
        )
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == HC_HEAT_COOL_COOL

    await hass.async_add_executor_job(
        acc.char_target_heat_cool.set_value, HC_HEAT_COOL_HEAT
    )
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
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVAC_MODE_COOL
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
    assert call_set_hvac_mode[1].data[ATTR_HVAC_MODE] == HVAC_MODE_HEAT


async def test_thermostat_hvac_modes_without_off(hass, hk_driver):
    """Test a thermostat that has no off."""
    entity_id = "climate.test"

    hass.states.async_set(
        entity_id, HVAC_MODE_AUTO, {ATTR_HVAC_MODES: [HVAC_MODE_AUTO, HVAC_MODE_HEAT]}
    )

    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()
    hap = acc.char_target_heat_cool.to_HAP()
    assert hap["valid-values"] == [1, 3]
    assert acc.char_target_heat_cool.value == 3

    await hass.async_add_executor_job(acc.char_target_heat_cool.set_value, 3)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 3

    await hass.async_add_executor_job(acc.char_target_heat_cool.set_value, 1)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1

    with pytest.raises(ValueError):
        await hass.async_add_executor_job(acc.char_target_heat_cool.set_value, 2)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1

    with pytest.raises(ValueError):
        await hass.async_add_executor_job(acc.char_target_heat_cool.set_value, 0)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1


async def test_thermostat_without_target_temp_only_range(hass, hk_driver, events):
    """Test a thermostat that only supports a range."""
    entity_id = "climate.test"

    # support_auto = True
    hass.states.async_set(
        entity_id,
        HVAC_MODE_OFF,
        {ATTR_SUPPORTED_FEATURES: SUPPORT_TARGET_TEMPERATURE_RANGE},
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
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
        HVAC_MODE_HEAT_COOL,
        {
            ATTR_TARGET_TEMP_HIGH: 22.0,
            ATTR_TARGET_TEMP_LOW: 20.0,
            ATTR_CURRENT_TEMPERATURE: 18.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_HEAT,
            ATTR_SUPPORTED_FEATURES: SUPPORT_TARGET_TEMPERATURE_RANGE,
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT,
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_FAN_ONLY,
                HVAC_MODE_COOL,
                HVAC_MODE_OFF,
                HVAC_MODE_AUTO,
            ],
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
        HVAC_MODE_COOL,
        {
            ATTR_TARGET_TEMP_HIGH: 23.0,
            ATTR_TARGET_TEMP_LOW: 19.0,
            ATTR_CURRENT_TEMPERATURE: 24.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_COOL,
            ATTR_SUPPORTED_FEATURES: SUPPORT_TARGET_TEMPERATURE_RANGE,
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT,
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_FAN_ONLY,
                HVAC_MODE_COOL,
                HVAC_MODE_OFF,
                HVAC_MODE_AUTO,
            ],
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
        HVAC_MODE_COOL,
        {
            ATTR_TARGET_TEMP_HIGH: 23.0,
            ATTR_TARGET_TEMP_LOW: 19.0,
            ATTR_CURRENT_TEMPERATURE: 21.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_IDLE,
            ATTR_SUPPORTED_FEATURES: SUPPORT_TARGET_TEMPERATURE_RANGE,
            ATTR_HVAC_MODES: [
                HVAC_MODE_HEAT,
                HVAC_MODE_HEAT_COOL,
                HVAC_MODE_FAN_ONLY,
                HVAC_MODE_COOL,
                HVAC_MODE_OFF,
                HVAC_MODE_AUTO,
            ],
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
        HVAC_MODE_HEAT,
        {
            ATTR_TARGET_TEMP_HIGH: 23.0,
            ATTR_TARGET_TEMP_LOW: 19.0,
            ATTR_CURRENT_TEMPERATURE: 21.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_IDLE,
            ATTR_SUPPORTED_FEATURES: SUPPORT_TARGET_TEMPERATURE_RANGE,
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


async def test_water_heater(hass, hk_driver, events):
    """Test if accessory and HA are updated accordingly."""
    entity_id = "water_heater.test"

    hass.states.async_set(entity_id, HVAC_MODE_HEAT)
    await hass.async_block_till_done()
    acc = WaterHeater(hass, hk_driver, "WaterHeater", entity_id, 2, None)
    await acc.run_handler()
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
        HVAC_MODE_HEAT,
        {
            ATTR_HVAC_MODE: HVAC_MODE_HEAT,
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
        entity_id, HVAC_MODE_HEAT_COOL, {ATTR_HVAC_MODE: HVAC_MODE_HEAT_COOL}
    )
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1
    assert acc.char_current_heat_cool.value == 1

    # Set from HomeKit
    call_set_temperature = async_mock_service(
        hass, DOMAIN_WATER_HEATER, "set_temperature"
    )

    await hass.async_add_executor_job(acc.char_target_temp.client_update_value, 52.0)
    await hass.async_block_till_done()
    assert call_set_temperature
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TEMPERATURE] == 52.0
    assert acc.char_target_temp.value == 52.0
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == f"52.0{TEMP_CELSIUS}"

    await hass.async_add_executor_job(acc.char_target_heat_cool.client_update_value, 0)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1

    await hass.async_add_executor_job(acc.char_target_heat_cool.client_update_value, 2)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1

    with pytest.raises(ValueError):
        await hass.async_add_executor_job(acc.char_target_heat_cool.set_value, 3)
    await hass.async_block_till_done()
    assert acc.char_target_heat_cool.value == 1


async def test_water_heater_fahrenheit(hass, hk_driver, events):
    """Test if accessory and HA are update accordingly."""
    entity_id = "water_heater.test"

    hass.states.async_set(entity_id, HVAC_MODE_HEAT)
    await hass.async_block_till_done()
    with patch.object(hass.config.units, CONF_TEMPERATURE_UNIT, new=TEMP_FAHRENHEIT):
        acc = WaterHeater(hass, hk_driver, "WaterHeater", entity_id, 2, None)
    await acc.run_handler()
    await hass.async_block_till_done()

    hass.states.async_set(entity_id, HVAC_MODE_HEAT, {ATTR_TEMPERATURE: 131})
    await hass.async_block_till_done()
    assert acc.char_target_temp.value == 55.0
    assert acc.char_current_temp.value == 50
    assert acc.char_display_units.value == 1

    # Set from HomeKit
    call_set_temperature = async_mock_service(
        hass, DOMAIN_WATER_HEATER, "set_temperature"
    )

    await hass.async_add_executor_job(acc.char_target_temp.client_update_value, 60)
    await hass.async_block_till_done()
    assert call_set_temperature
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TEMPERATURE] == 140.0
    assert acc.char_target_temp.value == 60.0
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "140.0°F"


async def test_water_heater_get_temperature_range(hass, hk_driver):
    """Test if temperature range is evaluated correctly."""
    entity_id = "water_heater.test"

    hass.states.async_set(entity_id, HVAC_MODE_HEAT)
    await hass.async_block_till_done()
    acc = WaterHeater(hass, hk_driver, "WaterHeater", entity_id, 2, None)

    hass.states.async_set(
        entity_id, HVAC_MODE_HEAT, {ATTR_MIN_TEMP: 20, ATTR_MAX_TEMP: 25}
    )
    await hass.async_block_till_done()
    assert acc.get_temperature_range() == (20, 25)

    acc._unit = TEMP_FAHRENHEIT
    hass.states.async_set(
        entity_id, HVAC_MODE_OFF, {ATTR_MIN_TEMP: 60, ATTR_MAX_TEMP: 70}
    )
    await hass.async_block_till_done()
    assert acc.get_temperature_range() == (15.5, 21.0)


async def test_water_heater_restore(hass, hk_driver, events):
    """Test setting up an entity from state in the event registry."""
    hass.state = CoreState.not_running

    registry = await entity_registry.async_get_registry(hass)

    registry.async_get_or_create(
        "water_heater", "generic", "1234", suggested_object_id="simple"
    )
    registry.async_get_or_create(
        "water_heater",
        "generic",
        "9012",
        suggested_object_id="all_info_set",
        capabilities={ATTR_MIN_TEMP: 60, ATTR_MAX_TEMP: 70},
        supported_features=0,
        device_class="mock-device-class",
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START, {})
    await hass.async_block_till_done()

    acc = Thermostat(hass, hk_driver, "WaterHeater", "water_heater.simple", 2, None)
    assert acc.category == 9
    assert acc.get_temperature_range() == (7, 35)
    assert set(acc.char_current_heat_cool.properties["ValidValues"].keys()) == {
        "Cool",
        "Heat",
        "Off",
    }

    acc = WaterHeater(
        hass, hk_driver, "WaterHeater", "water_heater.all_info_set", 2, None
    )
    assert acc.category == 9
    assert acc.get_temperature_range() == (60.0, 70.0)
    assert set(acc.char_current_heat_cool.properties["ValidValues"].keys()) == {
        "Cool",
        "Heat",
        "Off",
    }


async def test_thermostat_with_no_modes_when_we_first_see(hass, hk_driver, events):
    """Test if a thermostat that is not ready when we first see it."""
    entity_id = "climate.test"

    # support_auto = True
    hass.states.async_set(
        entity_id,
        HVAC_MODE_OFF,
        {
            ATTR_SUPPORTED_FEATURES: SUPPORT_TARGET_TEMPERATURE
            | SUPPORT_TARGET_TEMPERATURE_RANGE,
            ATTR_HVAC_MODES: [],
        },
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
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

    hass.states.async_set(
        entity_id,
        HVAC_MODE_HEAT_COOL,
        {
            ATTR_TARGET_TEMP_HIGH: 22.0,
            ATTR_TARGET_TEMP_LOW: 20.0,
            ATTR_CURRENT_TEMPERATURE: 18.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_HEAT,
            ATTR_HVAC_MODES: [HVAC_MODE_HEAT_COOL, HVAC_MODE_OFF, HVAC_MODE_AUTO],
        },
    )
    await hass.async_block_till_done()
    assert acc.char_heating_thresh_temp.value == 20.0
    assert acc.char_cooling_thresh_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 1
    assert acc.char_target_heat_cool.value == 3
    assert acc.char_current_temp.value == 18.0
    assert acc.char_display_units.value == 0


async def test_thermostat_with_no_off_after_recheck(hass, hk_driver, events):
    """Test if a thermostat that is not ready when we first see it that actually does not have off."""
    entity_id = "climate.test"

    # support_auto = True
    hass.states.async_set(
        entity_id,
        HVAC_MODE_COOL,
        {
            ATTR_SUPPORTED_FEATURES: SUPPORT_TARGET_TEMPERATURE
            | SUPPORT_TARGET_TEMPERATURE_RANGE,
            ATTR_HVAC_MODES: [],
        },
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
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

    hass.states.async_set(
        entity_id,
        HVAC_MODE_HEAT_COOL,
        {
            ATTR_TARGET_TEMP_HIGH: 22.0,
            ATTR_TARGET_TEMP_LOW: 20.0,
            ATTR_CURRENT_TEMPERATURE: 18.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_HEAT,
            ATTR_HVAC_MODES: [HVAC_MODE_HEAT_COOL, HVAC_MODE_AUTO],
        },
    )
    await hass.async_block_till_done()
    assert acc.char_heating_thresh_temp.value == 20.0
    assert acc.char_cooling_thresh_temp.value == 22.0
    assert acc.char_current_heat_cool.value == 1
    assert acc.char_target_heat_cool.value == 3
    assert acc.char_current_temp.value == 18.0
    assert acc.char_display_units.value == 0


async def test_thermostat_with_temp_clamps(hass, hk_driver, events):
    """Test that tempatures are clamped to valid values to prevent homekit crash."""
    entity_id = "climate.test"

    hass.states.async_set(
        entity_id,
        HVAC_MODE_COOL,
        {
            ATTR_SUPPORTED_FEATURES: SUPPORT_TARGET_TEMPERATURE
            | SUPPORT_TARGET_TEMPERATURE_RANGE,
            ATTR_HVAC_MODES: [],
            ATTR_MAX_TEMP: 50,
            ATTR_MIN_TEMP: 100,
        },
    )
    await hass.async_block_till_done()
    acc = Thermostat(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()

    assert acc.char_cooling_thresh_temp.value == 100
    assert acc.char_heating_thresh_temp.value == 100

    assert acc.char_cooling_thresh_temp.properties[PROP_MAX_VALUE] == 100
    assert acc.char_cooling_thresh_temp.properties[PROP_MIN_VALUE] == 100
    assert acc.char_cooling_thresh_temp.properties[PROP_MIN_STEP] == 0.1
    assert acc.char_heating_thresh_temp.properties[PROP_MAX_VALUE] == 100
    assert acc.char_heating_thresh_temp.properties[PROP_MIN_VALUE] == 100
    assert acc.char_heating_thresh_temp.properties[PROP_MIN_STEP] == 0.1

    assert acc.char_target_heat_cool.value == 2

    hass.states.async_set(
        entity_id,
        HVAC_MODE_HEAT_COOL,
        {
            ATTR_TARGET_TEMP_HIGH: 822.0,
            ATTR_TARGET_TEMP_LOW: 20.0,
            ATTR_CURRENT_TEMPERATURE: 9918.0,
            ATTR_HVAC_ACTION: CURRENT_HVAC_HEAT,
            ATTR_HVAC_MODES: [HVAC_MODE_HEAT_COOL, HVAC_MODE_AUTO],
        },
    )
    await hass.async_block_till_done()
    assert acc.char_heating_thresh_temp.value == 100.0
    assert acc.char_cooling_thresh_temp.value == 100.0
    assert acc.char_current_heat_cool.value == 1
    assert acc.char_target_heat_cool.value == 3
    assert acc.char_current_temp.value == 1000
    assert acc.char_display_units.value == 0
