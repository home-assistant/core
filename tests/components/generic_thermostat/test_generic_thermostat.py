"""The tests for the generic_thermostat."""
# pylint: disable=redefined-outer-name
import datetime
from asynctest import mock
import pytest
import pytz
import voluptuous as vol

from homeassistant.components import input_boolean
from homeassistant.components.climate.const import (
    ATTR_PRESET_MODE,
    ATTR_HVAC_MODES,
    DOMAIN,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_NONE,
    PRESET_COMFORT,
    PRESET_ECO,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.core as ha
from homeassistant.core import CoreState, State, callback
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM

from tests.common import assert_setup_component, mock_restore_cache
from tests.components.climate import common

CLIMATE_ENTITY = "climate.test"
ENTITY_SENSOR = "sensor.test"
ENTITY_HEATER = "switch.test_heater"
ENTITY_AC = "switch.test_ac"
ENTITY_HEATER_IB = "input_boolean.test_heater"
ENTITY_AC_IB = "input_boolean.test_ac"


async def test_setup_totally_missing_conf(hass):
    """Test set up generic_thermostat with missing config values."""
    with assert_setup_component(0, "climate"):
        await async_setup_component(
            hass,
            "climate",
            {"climate": {"platform": "generic_thermostat", "name": "test"}},
        )


async def test_setup_hvac_missing_conf(hass, caplog):
    """Test set up generic_thermostat with missing config values."""
    await async_setup_component(
        hass,
        "climate",
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
            }
        },
    )
    assert "You have to set at least one HVAC mode (heat or cold)" in caplog.text


async def test_setup_wrong_init_hvac_conf(hass, caplog):
    """Test set up generic_thermostat with missing config values."""
    await async_setup_component(
        hass,
        "climate",
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "heat": {"entity_id": ENTITY_HEATER},
                "initial_hvac_mode": "cool",
            }
        },
    )
    assert (
        "You cannot set an initial HVAC mode if you did not configure this mode"
        in caplog.text
    )


async def test_setup_missing_preset_away_conf(hass, caplog):
    """Test set up generic_thermostat with missing config values."""
    await async_setup_component(
        hass,
        "climate",
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "heat": {"entity_id": ENTITY_HEATER},
                "enabled_presets": [PRESET_AWAY],
            }
        },
    )
    assert (
        "For hvac mode heat, preset away is configured but away_temp is not set"
        in caplog.text
    )


async def test_setup_missing_preset_comfort_conf(hass, caplog):
    """Test set up generic_thermostat with missing config values."""
    await async_setup_component(
        hass,
        "climate",
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "cool": {"entity_id": ENTITY_AC},
                "enabled_presets": [PRESET_COMFORT],
            }
        },
    )
    assert (
        "For hvac mode cool, preset comfort is configured but comfort_shift is not set"
        in caplog.text
    )


async def test_setup_missing_preset_eco_conf(hass, caplog):
    """Test set up generic_thermostat with missing config values."""
    await async_setup_component(
        hass,
        "climate",
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "heat": {"entity_id": ENTITY_AC},
                "enabled_presets": ["eco"],
            }
        },
    )
    assert (
        "For hvac mode heat, preset eco is configured but eco_shift is not set"
        in caplog.text
    )


async def test_setup_no_heat_device_conf(hass, caplog):
    """Test set up generic_thermostat with missing config values."""
    with assert_setup_component(0, "climate"):
        await async_setup_component(
            hass,
            "climate",
            {
                "climate": {  # No heat device specified
                    "platform": "generic_thermostat",
                    "sensor": ENTITY_SENSOR,
                    "heat": {"min_temp": 18},
                }
            },
        )


async def test_setup_no_ac_device_conf(hass, caplog):
    """Test set up generic_thermostat with missing config values."""
    with assert_setup_component(0, "climate"):
        await async_setup_component(
            hass,
            "climate",
            {
                "climate": {  # No cool device specified
                    "platform": "generic_thermostat",
                    "sensor": ENTITY_SENSOR,
                    "cool": {"min_temp": 18},
                }
            },
        )


async def test_setup_missing_preset_conf(hass, caplog):
    """Test set up generic_thermostat with missing config values."""
    await async_setup_component(
        hass,
        "climate",
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "heat": {"entity_id": "switch.test"},
                "initial_preset_mode": "away",
            }
        },
    )
    assert (
        "There is no enabled presets and yet an initial_preset has been set"
        in caplog.text
    )


async def test_valid_conf(hass, caplog):
    """Test set up generic_thermostat with valid config values."""
    with assert_setup_component(2, "climate"):
        await async_setup_component(
            hass,
            "climate",
            {
                "climate": [
                    {
                        "platform": "generic_thermostat",
                        "sensor": ENTITY_SENSOR,
                        "heat": {"entity_id": ENTITY_HEATER},
                    },
                    {
                        "platform": "generic_thermostat",
                        "name": "Test 2",
                        "sensor": ENTITY_SENSOR,
                        "initial_hvac_mode": HVAC_MODE_OFF,
                        "initial_preset_mode": PRESET_NONE,
                        "hysteresis_tolerance_on": 0.5,
                        "hysteresis_tolerance_off": 1,
                        "restore_from_old_state": True,
                        "keep_alive": {"minutes": 3},
                        "min_cycle_duration": {"minutes": 5},
                        "enabled_presets": [PRESET_AWAY, PRESET_ECO, PRESET_COMFORT],
                        "heat": {
                            "entity_id": ENTITY_HEATER,
                            "min_temp": 15,
                            "max_temp": 24,
                            "initial_target_temp": 19,
                            "away_temp": 12,
                            "eco_shift": -2,
                            "comfort_shift": 2,
                        },
                        "cool": {
                            "entity_id": ENTITY_AC,
                            "min_temp": 10,
                            "max_temp": 32,
                            "initial_target_temp": 28,
                            "away_temp": 28,
                            "eco_shift": 4,
                            "comfort_shift": -2,
                        },
                    },
                ]
            },
        )
    assert "ERROR" not in caplog.text


def _send_time_changed(hass, newtime):
    """Send a time changed event."""
    hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: newtime})


@pytest.fixture
def setup_comp_1(hass):
    """Initialize components."""
    hass.config.units = METRIC_SYSTEM
    assert hass.loop.run_until_complete(
        async_setup_component(
            hass,
            "homeassistant",
            {"input_boolean": {"test_heater": None, "test_ac": None}},
        )
    )


async def setup_input_booleans(hass):
    """Initialize AC and heater components."""
    assert await async_setup_component(
        hass,
        input_boolean.DOMAIN,
        {"input_boolean": {"test_heater": None, "test_ac": None}},
    )


def _set_sensor_value(hass, temp):
    """Set up the test sensor."""
    hass.states.async_set(ENTITY_SENSOR, temp)


async def test_heater_input_boolean(hass, setup_comp_1, caplog):
    """Test heater switching input_boolean."""

    await setup_input_booleans(hass)

    # Set the temperature to 18
    _set_sensor_value(hass, 18)

    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "heat": {"entity_id": ENTITY_HEATER_IB, "initial_target_temp": 18},
                "initial_hvac_mode": HVAC_MODE_HEAT,
            }
        },
    )

    # Starts OFF
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state

    # Set the setpoint to 23
    await common.async_set_temperature(hass, 23, entity_id=CLIMATE_ENTITY)

    # The heater should turn ON
    assert STATE_ON == hass.states.get(ENTITY_HEATER_IB).state

    # Set the temperature to 25
    _set_sensor_value(hass, 25)
    await hass.async_block_till_done()

    # The heater should turn OFF
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state

    assert "ERROR" not in caplog.text


async def test_ac_input_boolean(hass, setup_comp_1, caplog):
    """Test AC switching input_boolean."""

    await setup_input_booleans(hass)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "cool": {"entity_id": ENTITY_AC_IB},
                "initial_hvac_mode": HVAC_MODE_COOL,
            }
        },
    )

    # Starts OFF
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    # Set the temperature to 18
    _set_sensor_value(hass, 18)
    await hass.async_block_till_done()

    # Set the setpoint to 23
    await common.async_set_temperature(hass, 23, entity_id=CLIMATE_ENTITY)

    # The heater should stay OFF
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    # Set the temperature to 25
    _set_sensor_value(hass, 25)
    await hass.async_block_till_done()

    # The heater should turn ON
    assert STATE_ON == hass.states.get(ENTITY_AC_IB).state

    assert "ERROR" not in caplog.text


async def test_change_hvac_mode(hass, setup_comp_1, caplog):
    """Test change hvac mode."""

    await setup_input_booleans(hass)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "heat": {"entity_id": ENTITY_HEATER_IB},
                "cool": {"entity_id": ENTITY_AC_IB},
                "initial_hvac_mode": HVAC_MODE_OFF,
            }
        },
    )

    # Set the temperature to 20
    _set_sensor_value(hass, 20)
    await hass.async_block_till_done()

    # Starts OFF
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state

    await common.async_set_temperature(
        hass, temperature=23, hvac_mode=HVAC_MODE_HEAT, entity_id=CLIMATE_ENTITY
    )
    await common.async_set_hvac_mode(hass, HVAC_MODE_HEAT, entity_id=CLIMATE_ENTITY)

    # The heater should be ON and the mode set to heat
    assert STATE_ON == hass.states.get(ENTITY_HEATER_IB).state
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state
    assert HVAC_MODE_HEAT == hass.states.get(CLIMATE_ENTITY).state

    # Resetting the same mode twice should not be a problem
    await common.async_set_hvac_mode(hass, HVAC_MODE_HEAT, entity_id=CLIMATE_ENTITY)
    assert HVAC_MODE_HEAT == hass.states.get(CLIMATE_ENTITY).state

    assert "ERROR" not in caplog.text


async def test_set_wrong_hvac_mode(hass, setup_comp_1, caplog):
    """Test set wrong hvac mode."""

    await setup_input_booleans(hass)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "cool": {"entity_id": ENTITY_AC_IB},
                "initial_hvac_mode": HVAC_MODE_OFF,
            }
        },
    )

    await hass.async_block_till_done()

    await common.async_set_hvac_mode(hass, HVAC_MODE_HEAT, entity_id=CLIMATE_ENTITY)

    assert "ERROR" in caplog.text
    assert "Unrecognized hvac mode" in caplog.text


async def test_set_wrong_preset_mode(hass, setup_comp_1, caplog):
    """Test set wrong preset mode."""

    await setup_input_booleans(hass)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "cool": {"entity_id": ENTITY_AC_IB, "away_temp": 31},
                "initial_hvac_mode": HVAC_MODE_OFF,
                "enabled_presets": ["away"],
            }
        },
    )

    await hass.async_block_till_done()

    await common.async_set_preset_mode(hass, PRESET_COMFORT, entity_id=CLIMATE_ENTITY)

    assert "ERROR" in caplog.text
    assert "This preset (comfort) is not enabled (see the configuration)" in caplog.text


async def test_restore_heat_state(hass, setup_comp_1, caplog):
    """Test restore state."""

    mock_restore_cache(
        hass,
        (
            State(
                CLIMATE_ENTITY,
                HVAC_MODE_HEAT,
                {
                    ATTR_HVAC_MODES: [HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_OFF],
                    ATTR_TEMPERATURE: 24,
                    ATTR_PRESET_MODE: PRESET_NONE,
                },
            ),
        ),
    )

    hass.state = CoreState.starting

    await setup_input_booleans(hass)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "heat": {"entity_id": ENTITY_HEATER_IB, "initial_target_temp": 21},
                "cool": {"entity_id": ENTITY_AC_IB},
                "initial_hvac_mode": HVAC_MODE_OFF,
                "restore_from_old_state": True,
            }
        },
    )

    await hass.async_block_till_done()

    assert HVAC_MODE_HEAT == hass.states.get(CLIMATE_ENTITY).state
    assert hass.states.get(CLIMATE_ENTITY).attributes.get(ATTR_TEMPERATURE) == 24

    assert "ERROR" not in caplog.text


async def test_restore_cool_state(hass, setup_comp_1, caplog):
    """Test restore state."""

    mock_restore_cache(
        hass,
        (
            State(
                CLIMATE_ENTITY,
                HVAC_MODE_COOL,
                {
                    ATTR_HVAC_MODES: [HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_OFF],
                    ATTR_TEMPERATURE: 28,
                    ATTR_PRESET_MODE: PRESET_NONE,
                },
            ),
        ),
    )

    hass.state = CoreState.starting

    await setup_input_booleans(hass)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "heat": {"entity_id": ENTITY_HEATER_IB, "initial_target_temp": 21},
                "cool": {"entity_id": ENTITY_AC_IB},
                "initial_hvac_mode": HVAC_MODE_OFF,
                "restore_from_old_state": True,
            }
        },
    )

    await hass.async_block_till_done()

    assert HVAC_MODE_COOL == hass.states.get(CLIMATE_ENTITY).state
    assert hass.states.get(CLIMATE_ENTITY).attributes.get(ATTR_TEMPERATURE) == 28

    assert "ERROR" not in caplog.text


async def test_preset_mode_away(hass, setup_comp_1, caplog):
    """Test preset mode away."""

    await setup_input_booleans(hass)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "cool": {"entity_id": ENTITY_AC_IB, "away_temp": 30},
                "heat": {"entity_id": ENTITY_HEATER_IB, "away_temp": 30},
                "initial_hvac_mode": HVAC_MODE_COOL,
                "enabled_presets": [PRESET_AWAY],
            }
        },
    )

    # Start OFF
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    # Set the temperature to 18
    _set_sensor_value(hass, 18)
    await hass.async_block_till_done()

    # Set the setpoint to 23
    await common.async_set_temperature(
        hass, temperature=23, entity_id=CLIMATE_ENTITY, hvac_mode=HVAC_MODE_COOL
    )

    # The device should stay OFF
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    # Set the temperature to 25
    _set_sensor_value(hass, 25)
    await hass.async_block_till_done()

    # The device should turn ON
    assert STATE_ON == hass.states.get(ENTITY_AC_IB).state

    await common.async_set_preset_mode(hass, PRESET_AWAY, entity_id=CLIMATE_ENTITY)
    await hass.async_block_till_done()

    # The device should turn OFF since the away_temp is 30
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    # Set the temperature to 28
    _set_sensor_value(hass, 28)
    await hass.async_block_till_done()

    # The device should stay OFF since the away_temp is still 30
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    # Set the setpoint to 21 for cool mode
    await common.async_set_temperature(
        hass, temperature=21, entity_id=CLIMATE_ENTITY, hvac_mode=HVAC_MODE_COOL
    )
    # Set the setpoint to 21 for heat mode
    await common.async_set_temperature(
        hass, temperature=21, entity_id=CLIMATE_ENTITY, hvac_mode=HVAC_MODE_HEAT
    )

    # The device should stay OFF since the away_temp is still 30
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    # Switch to heat with no errors
    await common.async_set_hvac_mode(hass, HVAC_MODE_HEAT, entity_id=CLIMATE_ENTITY)

    assert "ERROR" not in caplog.text


async def test_set_wrong_temperature(hass, setup_comp_1, caplog):
    """Test set wrong temperature."""

    await setup_input_booleans(hass)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "heat": {"entity_id": ENTITY_HEATER_IB, "initial_target_temp": 25},
                "initial_hvac_mode": HVAC_MODE_HEAT,
            }
        },
    )

    await hass.async_block_till_done()

    assert hass.states.get(CLIMATE_ENTITY).attributes.get(ATTR_TEMPERATURE) == 25

    # Update to disabled mode
    await common.async_set_temperature(
        hass, temperature=24, hvac_mode=HVAC_MODE_COOL, entity_id=CLIMATE_ENTITY
    )
    await hass.async_block_till_done()
    assert (
        "Try to update temperature to 24.0 for mode cool but this mode is not enabled. Skipping."
        in caplog.text
    )
    assert hass.states.get(CLIMATE_ENTITY).attributes.get(ATTR_TEMPERATURE) == 25

    # Update to OFF mode
    await common.async_set_temperature(
        hass, temperature=24, hvac_mode=HVAC_MODE_OFF, entity_id=CLIMATE_ENTITY
    )
    await hass.async_block_till_done()
    assert "You cannot update temperature for OFF mode" in caplog.text
    assert hass.states.get(CLIMATE_ENTITY).attributes.get(ATTR_TEMPERATURE) == 25

    assert "ERROR" not in caplog.text

    # Update to unknown mode
    try:
        await common.async_set_temperature(
            hass, temperature=24, hvac_mode="WTF", entity_id=CLIMATE_ENTITY
        )
        assert False, "Should have raised a voluptuous error"
    except vol.error.MultipleInvalid:
        pass


async def test_set_wrong_current_temperature(hass, setup_comp_1, caplog):
    """Test set wrong current temperature."""

    await setup_input_booleans(hass)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "heat": {"entity_id": ENTITY_HEATER_IB},
                "initial_hvac_mode": HVAC_MODE_HEAT,
            }
        },
    )

    # Set the temperature to None
    _set_sensor_value(hass, None)
    await hass.async_block_till_done()

    _set_sensor_value(hass, False)
    await hass.async_block_till_done()

    assert (
        "Unable to update from sensor: could not convert string to float: 'False'"
        in caplog.text
    )


async def test_set_wrong_switch_state(hass, setup_comp_1, caplog):
    """Test set wrong current temperature."""

    await setup_input_booleans(hass)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "heat": {"entity_id": ENTITY_HEATER_IB, "initial_target_temp": 25},
                "initial_hvac_mode": HVAC_MODE_HEAT,
            }
        },
    )

    hass.states.async_set(ENTITY_HEATER_IB, None)

    assert "ERROR" not in caplog.text


async def test_normal_operate(hass, setup_comp_1, caplog):
    """Test normal operate (temperature set and switch mode)."""

    await setup_input_booleans(hass)

    # Set the temperature to 22
    _set_sensor_value(hass, 22)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "heat": {"entity_id": ENTITY_HEATER_IB, "initial_target_temp": 21},
                "cool": {"entity_id": ENTITY_AC_IB, "initial_target_temp": 26},
                "initial_hvac_mode": HVAC_MODE_HEAT,
            }
        },
    )

    # Force the IB to ON
    hass.states.async_set(ENTITY_HEATER_IB, STATE_ON)
    hass.states.async_set(ENTITY_AC_IB, STATE_ON)

    assert STATE_ON == hass.states.get(ENTITY_HEATER_IB).state
    assert STATE_ON == hass.states.get(ENTITY_AC_IB).state

    # Switch to OFF, the IB should switch to OFF
    await common.async_set_hvac_mode(hass, HVAC_MODE_OFF, entity_id=CLIMATE_ENTITY)
    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    # Switch to heat, the IB should stay to OFF since the temperature is 22 and the target 21
    await common.async_set_hvac_mode(hass, HVAC_MODE_HEAT, entity_id=CLIMATE_ENTITY)
    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    # Switch to cool, the IB should stay to OFF since the temperature is 22 and the target 28
    await common.async_set_hvac_mode(hass, HVAC_MODE_COOL, entity_id=CLIMATE_ENTITY)
    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    # Set the temperature to 35, the AC device should turn ON
    _set_sensor_value(hass, 35)
    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state
    assert STATE_ON == hass.states.get(ENTITY_AC_IB).state

    # Switch to heat, all devices should turn OFF
    await common.async_set_hvac_mode(hass, HVAC_MODE_HEAT, entity_id=CLIMATE_ENTITY)
    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    # Set the temperature to 18, the heater device should turn ON
    _set_sensor_value(hass, 18)
    await hass.async_block_till_done()
    assert STATE_ON == hass.states.get(ENTITY_HEATER_IB).state
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    assert "ERROR" not in caplog.text


async def test_heat_hysteresis_tolerance(hass, setup_comp_1, caplog):
    """Test heat hysteresis tolerance operation."""

    await setup_input_booleans(hass)

    # Set the temperature to 22
    _set_sensor_value(hass, 22)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "hysteresis_tolerance_on": 0.5,
                "hysteresis_tolerance_off": 2,
                "heat": {"entity_id": ENTITY_HEATER_IB, "initial_target_temp": 21},
                "initial_hvac_mode": HVAC_MODE_HEAT,
            }
        },
    )

    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state

    # Set the temperature to 20.6, the device should stay OFF because we are not <= 0.5
    _set_sensor_value(hass, 20.6)
    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state

    # Set the temperature to 20, the device should turn ON
    _set_sensor_value(hass, 20)
    await hass.async_block_till_done()
    assert STATE_ON == hass.states.get(ENTITY_HEATER_IB).state

    # Set the temperature to 23, the device should stay ON because we are not > 2
    _set_sensor_value(hass, 23)
    await hass.async_block_till_done()
    assert STATE_ON == hass.states.get(ENTITY_HEATER_IB).state

    # Set the temperature to 23.5, the device should turn OFF
    _set_sensor_value(hass, 23.5)
    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state

    assert "ERROR" not in caplog.text


async def test_cool_hysteresis_tolerance(hass, setup_comp_1, caplog):
    """Test cool hysteresis tolerance operation."""

    await setup_input_booleans(hass)

    # Set the temperature to 24
    _set_sensor_value(hass, 24)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "hysteresis_tolerance_on": 0.5,
                "hysteresis_tolerance_off": 2,
                "cool": {"entity_id": ENTITY_AC_IB, "initial_target_temp": 25},
                "initial_hvac_mode": HVAC_MODE_COOL,
            }
        },
    )

    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    # Set the temperature to 25.4, the device should stay OFF because we are not >= 0.5
    _set_sensor_value(hass, 25.4)
    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    # Set the temperature to 26, the device should turn ON
    _set_sensor_value(hass, 26)
    await hass.async_block_till_done()
    assert STATE_ON == hass.states.get(ENTITY_AC_IB).state

    # Set the temperature to 23, the device should stay ON because we are not > 2
    _set_sensor_value(hass, 23)
    await hass.async_block_till_done()
    assert STATE_ON == hass.states.get(ENTITY_AC_IB).state

    # Set the temperature to 22.5, the device should turn OFF
    _set_sensor_value(hass, 22.5)
    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    assert "ERROR" not in caplog.text


async def test_heat_comfort_eco(hass, setup_comp_1, caplog):
    """Test heat comfort/eco operation."""

    await setup_input_booleans(hass)

    # Set the temperature to 22
    _set_sensor_value(hass, 22)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "hysteresis_tolerance_on": 0,
                "hysteresis_tolerance_off": 0,
                "heat": {
                    "entity_id": ENTITY_HEATER_IB,
                    "initial_target_temp": 21,
                    "comfort_shift": 3,
                    "eco_shift": -5,
                    "away_temp": 12,
                },
                "initial_hvac_mode": HVAC_MODE_HEAT,
                "initial_preset_mode": PRESET_COMFORT,
                "enabled_presets": [PRESET_AWAY, PRESET_COMFORT, PRESET_ECO],
            }
        },
    )

    await hass.async_block_till_done()

    # Preset should be comfort
    assert (
        hass.states.get(CLIMATE_ENTITY).attributes.get(ATTR_PRESET_MODE)
        == PRESET_COMFORT
    )

    # Target temp should be 21 + 3 = 24
    assert hass.states.get(CLIMATE_ENTITY).attributes.get(ATTR_TEMPERATURE) == 24

    # The heater should be ON
    assert STATE_ON == hass.states.get(ENTITY_HEATER_IB).state

    # Set the temperature to 24.5, the device should turn OFF
    _set_sensor_value(hass, 24.5)
    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state

    # Set the temperature to 23.5, the device should turn ON
    _set_sensor_value(hass, 23.5)
    await hass.async_block_till_done()
    assert STATE_ON == hass.states.get(ENTITY_HEATER_IB).state

    # Activate ECO mode, the target temp is now 16
    await common.async_set_preset_mode(hass, PRESET_ECO, entity_id=CLIMATE_ENTITY)
    await hass.async_block_till_done()

    # Preset should be eco
    assert (
        hass.states.get(CLIMATE_ENTITY).attributes.get(ATTR_PRESET_MODE) == PRESET_ECO
    )

    # Target temp should be 21 + (-5) = 16
    assert hass.states.get(CLIMATE_ENTITY).attributes.get(ATTR_TEMPERATURE) == 16

    # The heater should turn OFF
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state

    # Set the temperature to 15.5, the device should turn ON
    _set_sensor_value(hass, 15.5)
    await hass.async_block_till_done()
    assert STATE_ON == hass.states.get(ENTITY_HEATER_IB).state

    assert "ERROR" not in caplog.text


async def test_cool_comfort_eco(hass, setup_comp_1, caplog):
    """Test cool comfort/eco operation."""

    await setup_input_booleans(hass)

    # Set the temperature to 28
    _set_sensor_value(hass, 28)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "hysteresis_tolerance_on": 0,
                "hysteresis_tolerance_off": 0,
                "cool": {
                    "entity_id": ENTITY_AC_IB,
                    "initial_target_temp": 28,
                    "comfort_shift": -3,
                    "eco_shift": 10,
                    "away_temp": 28,
                },
                "initial_hvac_mode": HVAC_MODE_COOL,
                "initial_preset_mode": PRESET_ECO,
                "enabled_presets": [PRESET_AWAY, PRESET_COMFORT, PRESET_ECO],
            }
        },
    )

    await hass.async_block_till_done()

    # Preset should be eco
    assert (
        hass.states.get(CLIMATE_ENTITY).attributes.get(ATTR_PRESET_MODE) == PRESET_ECO
    )

    # Target temp should be 28 + 10 = 38
    assert hass.states.get(CLIMATE_ENTITY).attributes.get(ATTR_TEMPERATURE) == 38

    # The device should be OFF
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    # Activate comfort mode, the target temp is now 28 - 3 = 25
    await common.async_set_preset_mode(hass, PRESET_COMFORT, entity_id=CLIMATE_ENTITY)
    await hass.async_block_till_done()

    # Preset should be comfort
    assert (
        hass.states.get(CLIMATE_ENTITY).attributes.get(ATTR_PRESET_MODE)
        == PRESET_COMFORT
    )

    # Target temp should be 25
    assert hass.states.get(CLIMATE_ENTITY).attributes.get(ATTR_TEMPERATURE) == 25

    # The device should turn ON
    assert STATE_ON == hass.states.get(ENTITY_AC_IB).state

    assert "ERROR" not in caplog.text


async def test_keep_alive_interval(hass, setup_comp_1, caplog):
    """Test keep alive interval feature."""

    await setup_input_booleans(hass)

    # Set the temperature to 21
    _set_sensor_value(hass, 21)

    start_time = datetime.datetime.now(pytz.UTC)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "hysteresis_tolerance_on": 0,
                "hysteresis_tolerance_off": 0,
                "keep_alive": {"minutes": 10},
                "heat": {"entity_id": ENTITY_HEATER_IB, "initial_target_temp": 21},
                "initial_hvac_mode": HVAC_MODE_HEAT,
            }
        },
    )

    calls = []

    @callback
    def count_call(call):
        """Count calls to service turn_on / turn_off."""
        calls.append(call)

    hass.services.async_register(ha.DOMAIN, SERVICE_TURN_ON, count_call)
    hass.services.async_register(ha.DOMAIN, SERVICE_TURN_OFF, count_call)

    await hass.async_block_till_done()

    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state
    assert not calls
    _send_time_changed(hass, start_time + datetime.timedelta(minutes=5))
    await hass.async_block_till_done()
    assert not calls
    _send_time_changed(hass, start_time + datetime.timedelta(minutes=11))
    await hass.async_block_till_done()
    assert len(calls) == 1

    assert "ERROR" not in caplog.text


async def test_min_cycle_duration_disabled(hass, setup_comp_1, caplog):
    """Test min cycle duration feature (disabled)."""

    await setup_input_booleans(hass)

    # Set the temperature to 21
    _set_sensor_value(hass, 21)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "hysteresis_tolerance_on": 0,
                "hysteresis_tolerance_off": 0,
                "min_cycle_duration": {"minutes": 0},
                "heat": {"entity_id": ENTITY_HEATER_IB, "initial_target_temp": 21},
                "cool": {"entity_id": ENTITY_AC_IB, "initial_target_temp": 28},
                "initial_hvac_mode": HVAC_MODE_HEAT,
            }
        },
    )

    # Test if flapping is allowed with min cycle duration to 0
    _set_sensor_value(hass, 21.1)
    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state

    _set_sensor_value(hass, 21.2)
    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state
    assert "Heater already OFF" in caplog.text

    _set_sensor_value(hass, 20.9)
    await hass.async_block_till_done()
    assert STATE_ON == hass.states.get(ENTITY_HEATER_IB).state

    _set_sensor_value(hass, 21.1)
    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state

    _set_sensor_value(hass, 20.9)
    await hass.async_block_till_done()
    assert STATE_ON == hass.states.get(ENTITY_HEATER_IB).state

    _set_sensor_value(hass, 20.8)
    await hass.async_block_till_done()
    assert STATE_ON == hass.states.get(ENTITY_HEATER_IB).state
    assert "Heater already ON" in caplog.text

    # Switch to cool
    await common.async_set_hvac_mode(hass, HVAC_MODE_COOL, entity_id=CLIMATE_ENTITY)
    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    # Test if flapping is allowed with min cycle duration to 0
    _set_sensor_value(hass, 27.9)
    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    _set_sensor_value(hass, 27.8)
    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state
    assert "AC already OFF" in caplog.text

    _set_sensor_value(hass, 28.1)
    await hass.async_block_till_done()
    assert STATE_ON == hass.states.get(ENTITY_AC_IB).state

    _set_sensor_value(hass, 27.9)
    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    _set_sensor_value(hass, 28.1)
    await hass.async_block_till_done()
    assert STATE_ON == hass.states.get(ENTITY_AC_IB).state

    _set_sensor_value(hass, 28.2)
    await hass.async_block_till_done()
    assert STATE_ON == hass.states.get(ENTITY_AC_IB).state
    assert "AC already ON" in caplog.text

    assert "ERROR" not in caplog.text


async def test_min_cycle_duration_enabled(hass, setup_comp_1, caplog):
    """Test min cycle duration feature (enabled)."""

    await setup_input_booleans(hass)

    # Set the temperature to 21
    _set_sensor_value(hass, 21)

    start_time = datetime.datetime.now(pytz.UTC)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "hysteresis_tolerance_on": 0,
                "hysteresis_tolerance_off": 0,
                "min_cycle_duration": {"minutes": 10},
                "heat": {"entity_id": ENTITY_HEATER_IB, "initial_target_temp": 21},
                "cool": {"entity_id": ENTITY_AC_IB, "initial_target_temp": 28},
                "initial_hvac_mode": HVAC_MODE_HEAT,
            }
        },
    )

    # Test if flapping is disallowed with min cycle duration to 10
    _set_sensor_value(hass, 21.1)
    await hass.async_block_till_done()
    assert STATE_ON == hass.states.get(ENTITY_HEATER_IB).state

    _set_sensor_value(hass, 20.9)
    await hass.async_block_till_done()
    assert STATE_ON == hass.states.get(ENTITY_HEATER_IB).state

    _set_sensor_value(hass, 21.1)
    await hass.async_block_till_done()
    assert STATE_ON == hass.states.get(ENTITY_HEATER_IB).state

    _set_sensor_value(hass, 20.9)
    await hass.async_block_till_done()
    assert STATE_ON == hass.states.get(ENTITY_HEATER_IB).state

    future = datetime.datetime.now(pytz.UTC) + datetime.timedelta(minutes=11)
    with mock.patch("homeassistant.util.dt.utcnow", return_value=future):
        # Same test with 10+ minutes delay between each call
        await hass.async_block_till_done()
        _set_sensor_value(hass, 21.2)
        await hass.async_block_till_done()
        assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state
        await hass.async_block_till_done()

        _send_time_changed(hass, start_time + datetime.timedelta(minutes=21))
        await hass.async_block_till_done()
        _set_sensor_value(hass, 20.9)
        await hass.async_block_till_done()
        assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state

    assert "ERROR" not in caplog.text


async def test_off_min_cycle_duration_enabled(hass, setup_comp_1, caplog):
    """Test off during min cycle duration feature (enabled)."""

    await setup_input_booleans(hass)

    # Set the temperature to 21
    _set_sensor_value(hass, 21)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "hysteresis_tolerance_on": 0,
                "hysteresis_tolerance_off": 0,
                "min_cycle_duration": {"minutes": 10},
                "heat": {"entity_id": ENTITY_HEATER_IB, "initial_target_temp": 21},
                "cool": {"entity_id": ENTITY_AC_IB, "initial_target_temp": 28},
                "initial_hvac_mode": HVAC_MODE_HEAT,
            }
        },
    )

    assert STATE_ON == hass.states.get(ENTITY_HEATER_IB).state
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    # Switch to OFF
    await common.async_set_hvac_mode(hass, HVAC_MODE_OFF, entity_id=CLIMATE_ENTITY)
    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state
    assert STATE_OFF == hass.states.get(ENTITY_AC_IB).state

    assert "ERROR" not in caplog.text


async def test_b4dpxl_case(hass, setup_comp_1, caplog):
    """Test b4dpxl case.

    https://github.com/home-assistant/home-assistant/pull/27833#issuecomment-544477918
    """

    await setup_input_booleans(hass)

    # Set the temperature to 20
    _set_sensor_value(hass, 20)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "sensor": ENTITY_SENSOR,
                "hysteresis_tolerance_on": 0,
                "hysteresis_tolerance_off": 0,
                "heat": {"entity_id": ENTITY_HEATER_IB, "away_temp": 12},
                "initial_hvac_mode": HVAC_MODE_HEAT,
                "initial_preset_mode": PRESET_AWAY,
                "enabled_presets": [PRESET_AWAY],
            }
        },
    )

    # Start OFF
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state

    # Preset should be away
    assert (
        hass.states.get(CLIMATE_ENTITY).attributes.get(ATTR_PRESET_MODE) == PRESET_AWAY
    )

    # Set the setpoint to 19
    await common.async_set_temperature(
        hass, temperature=19, entity_id=CLIMATE_ENTITY, hvac_mode=HVAC_MODE_HEAT
    )

    # The device should stay OFF
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state

    # Set the temperature to 18
    _set_sensor_value(hass, 18)
    await hass.async_block_till_done()

    # The device should stay OFF
    assert STATE_OFF == hass.states.get(ENTITY_HEATER_IB).state

    # Set the temperature to 11
    _set_sensor_value(hass, 11)
    await hass.async_block_till_done()

    # The device should turn ON
    assert STATE_ON == hass.states.get(ENTITY_HEATER_IB).state

    assert "ERROR" not in caplog.text
