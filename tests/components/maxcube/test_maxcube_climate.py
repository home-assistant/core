"""Test EQ3 Max! Thermostats."""
from datetime import timedelta

from maxcube.cube import MaxCube
from maxcube.device import (
    MAX_DEVICE_MODE_AUTOMATIC,
    MAX_DEVICE_MODE_BOOST,
    MAX_DEVICE_MODE_MANUAL,
    MAX_DEVICE_MODE_VACATION,
)
from maxcube.thermostat import MaxThermostat
from maxcube.wallthermostat import MaxWallThermostat
import pytest

from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    DOMAIN as CLIMATE_DOMAIN,
    HVAC_MODE_AUTO,
    HVAC_MODE_DRY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.maxcube.climate import (
    MAX_TEMPERATURE,
    MIN_TEMPERATURE,
    OFF_TEMPERATURE,
    ON_TEMPERATURE,
    PRESET_ON,
    SUPPORT_FLAGS,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.util import utcnow

from tests.common import async_fire_time_changed

ENTITY_ID = "climate.testroom_testthermostat"
WALL_ENTITY_ID = "climate.testroom_testwallthermostat"
VALVE_POSITION = "valve_position"


async def test_setup_thermostat(hass, cube: MaxCube):
    """Test a successful setup of a thermostat device."""
    entity_registry = er.async_get(hass)
    assert entity_registry.async_is_registered(ENTITY_ID)
    entity = entity_registry.async_get(ENTITY_ID)
    assert entity.unique_id == "AABBCCDD01"

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVAC_MODE_AUTO
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "TestRoom TestThermostat"
    assert state.attributes.get(ATTR_HVAC_ACTION) == CURRENT_HVAC_HEAT
    assert state.attributes.get(ATTR_HVAC_MODES) == [
        HVAC_MODE_OFF,
        HVAC_MODE_AUTO,
        HVAC_MODE_HEAT,
    ]
    assert state.attributes.get(ATTR_PRESET_MODES) == [
        PRESET_NONE,
        PRESET_BOOST,
        PRESET_COMFORT,
        PRESET_ECO,
        PRESET_AWAY,
        PRESET_ON,
    ]
    assert state.attributes.get(ATTR_PRESET_MODE) == PRESET_NONE
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == SUPPORT_FLAGS
    assert state.attributes.get(ATTR_MAX_TEMP) == MAX_TEMPERATURE
    assert state.attributes.get(ATTR_MIN_TEMP) == 5.0
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 19.0
    assert state.attributes.get(ATTR_TEMPERATURE) == 20.5
    assert state.attributes.get(VALVE_POSITION) == 25


async def test_setup_wallthermostat(hass, cube: MaxCube):
    """Test a successful setup of a wall thermostat device."""
    entity_registry = er.async_get(hass)
    assert entity_registry.async_is_registered(WALL_ENTITY_ID)
    entity = entity_registry.async_get(WALL_ENTITY_ID)
    assert entity.unique_id == "AABBCCDD02"

    state = hass.states.get(WALL_ENTITY_ID)
    assert state.state == HVAC_MODE_OFF
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "TestRoom TestWallThermostat"
    assert state.attributes.get(ATTR_HVAC_ACTION) == CURRENT_HVAC_HEAT
    assert state.attributes.get(ATTR_PRESET_MODE) == PRESET_NONE
    assert state.attributes.get(ATTR_MAX_TEMP) == 29.0
    assert state.attributes.get(ATTR_MIN_TEMP) == 5.0
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 19.0
    assert state.attributes.get(ATTR_TEMPERATURE) is None


async def test_thermostat_set_hvac_mode_off(
    hass, cube: MaxCube, thermostat: MaxThermostat
):
    """Turn off thermostat."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVAC_MODE_OFF},
        blocking=True,
    )
    cube.set_temperature_mode.assert_called_once_with(
        thermostat, OFF_TEMPERATURE, MAX_DEVICE_MODE_MANUAL
    )

    thermostat.mode = MAX_DEVICE_MODE_MANUAL
    thermostat.target_temperature = OFF_TEMPERATURE
    thermostat.valve_position = 0

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVAC_MODE_OFF
    assert state.attributes.get(ATTR_TEMPERATURE) is None
    assert state.attributes.get(ATTR_HVAC_ACTION) == CURRENT_HVAC_OFF
    assert state.attributes.get(VALVE_POSITION) == 0

    wall_state = hass.states.get(WALL_ENTITY_ID)
    assert wall_state.attributes.get(ATTR_HVAC_ACTION) == CURRENT_HVAC_OFF


async def test_thermostat_set_hvac_mode_heat(
    hass, cube: MaxCube, thermostat: MaxThermostat
):
    """Set hvac mode to heat."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVAC_MODE_HEAT},
        blocking=True,
    )
    cube.set_temperature_mode.assert_called_once_with(
        thermostat, 20.5, MAX_DEVICE_MODE_MANUAL
    )
    thermostat.mode = MAX_DEVICE_MODE_MANUAL

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVAC_MODE_HEAT


async def test_thermostat_set_invalid_hvac_mode(
    hass, cube: MaxCube, thermostat: MaxThermostat
):
    """Set hvac mode to heat."""
    with pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVAC_MODE_DRY},
            blocking=True,
        )
    cube.set_temperature_mode.assert_not_called()


async def test_thermostat_set_temperature(
    hass, cube: MaxCube, thermostat: MaxThermostat
):
    """Set hvac mode to heat."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 10.0},
        blocking=True,
    )
    cube.set_temperature_mode.assert_called_once_with(thermostat, 10.0, None)
    thermostat.target_temperature = 10.0
    thermostat.valve_position = 0

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVAC_MODE_AUTO
    assert state.attributes.get(ATTR_TEMPERATURE) == 10.0
    assert state.attributes.get(ATTR_HVAC_ACTION) == CURRENT_HVAC_IDLE


async def test_thermostat_set_no_temperature(
    hass, cube: MaxCube, thermostat: MaxThermostat
):
    """Set hvac mode to heat."""
    with pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_TARGET_TEMP_HIGH: 29.0,
                ATTR_TARGET_TEMP_LOW: 10.0,
            },
            blocking=True,
        )
        cube.set_temperature_mode.assert_not_called()


async def test_thermostat_set_preset_on(hass, cube: MaxCube, thermostat: MaxThermostat):
    """Set preset mode to on."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_ON},
        blocking=True,
    )

    cube.set_temperature_mode.assert_called_once_with(
        thermostat, ON_TEMPERATURE, MAX_DEVICE_MODE_MANUAL
    )
    thermostat.mode = MAX_DEVICE_MODE_MANUAL
    thermostat.target_temperature = ON_TEMPERATURE

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes.get(ATTR_TEMPERATURE) is None
    assert state.attributes.get(ATTR_PRESET_MODE) == PRESET_ON


async def test_thermostat_set_preset_comfort(
    hass, cube: MaxCube, thermostat: MaxThermostat
):
    """Set preset mode to comfort."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_COMFORT},
        blocking=True,
    )
    cube.set_temperature_mode.assert_called_once_with(
        thermostat, thermostat.comfort_temperature, MAX_DEVICE_MODE_MANUAL
    )
    thermostat.mode = MAX_DEVICE_MODE_MANUAL
    thermostat.target_temperature = thermostat.comfort_temperature

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes.get(ATTR_TEMPERATURE) == thermostat.comfort_temperature
    assert state.attributes.get(ATTR_PRESET_MODE) == PRESET_COMFORT


async def test_thermostat_set_preset_eco(
    hass, cube: MaxCube, thermostat: MaxThermostat
):
    """Set preset mode to eco."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_ECO},
        blocking=True,
    )
    cube.set_temperature_mode.assert_called_once_with(
        thermostat, thermostat.eco_temperature, MAX_DEVICE_MODE_MANUAL
    )
    thermostat.mode = MAX_DEVICE_MODE_MANUAL
    thermostat.target_temperature = thermostat.eco_temperature

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes.get(ATTR_TEMPERATURE) == thermostat.eco_temperature
    assert state.attributes.get(ATTR_PRESET_MODE) == PRESET_ECO


async def test_thermostat_set_preset_away(
    hass, cube: MaxCube, thermostat: MaxThermostat
):
    """Set preset mode to away."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )
    cube.set_temperature_mode.assert_called_once_with(
        thermostat, None, MAX_DEVICE_MODE_VACATION
    )
    thermostat.mode = MAX_DEVICE_MODE_VACATION
    thermostat.target_temperature = thermostat.eco_temperature

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes.get(ATTR_TEMPERATURE) == thermostat.eco_temperature
    assert state.attributes.get(ATTR_PRESET_MODE) == PRESET_AWAY


async def test_thermostat_set_preset_boost(
    hass, cube: MaxCube, thermostat: MaxThermostat
):
    """Set preset mode to boost."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_BOOST},
        blocking=True,
    )
    cube.set_temperature_mode.assert_called_once_with(
        thermostat, None, MAX_DEVICE_MODE_BOOST
    )
    thermostat.mode = MAX_DEVICE_MODE_BOOST
    thermostat.target_temperature = thermostat.eco_temperature

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVAC_MODE_AUTO
    assert state.attributes.get(ATTR_TEMPERATURE) == thermostat.eco_temperature
    assert state.attributes.get(ATTR_PRESET_MODE) == PRESET_BOOST


async def test_thermostat_set_preset_none(
    hass, cube: MaxCube, thermostat: MaxThermostat
):
    """Set preset mode to boost."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )
    cube.set_temperature_mode.assert_called_once_with(
        thermostat, None, MAX_DEVICE_MODE_AUTOMATIC
    )


async def test_thermostat_set_invalid_preset(
    hass, cube: MaxCube, thermostat: MaxThermostat
):
    """Set hvac mode to heat."""
    with pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: "invalid"},
            blocking=True,
        )
    cube.set_temperature_mode.assert_not_called()


async def test_wallthermostat_set_hvac_mode_heat(
    hass, cube: MaxCube, wallthermostat: MaxWallThermostat
):
    """Set wall thermostat hvac mode to heat."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: WALL_ENTITY_ID, ATTR_HVAC_MODE: HVAC_MODE_HEAT},
        blocking=True,
    )
    cube.set_temperature_mode.assert_called_once_with(
        wallthermostat, MIN_TEMPERATURE, MAX_DEVICE_MODE_MANUAL
    )
    wallthermostat.target_temperature = MIN_TEMPERATURE

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()

    state = hass.states.get(WALL_ENTITY_ID)
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes.get(ATTR_TEMPERATURE) == MIN_TEMPERATURE


async def test_wallthermostat_set_hvac_mode_auto(
    hass, cube: MaxCube, wallthermostat: MaxWallThermostat
):
    """Set wall thermostat hvac mode to auto."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: WALL_ENTITY_ID, ATTR_HVAC_MODE: HVAC_MODE_AUTO},
        blocking=True,
    )
    cube.set_temperature_mode.assert_called_once_with(
        wallthermostat, None, MAX_DEVICE_MODE_AUTOMATIC
    )
    wallthermostat.mode = MAX_DEVICE_MODE_AUTOMATIC
    wallthermostat.target_temperature = 23.0

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()

    state = hass.states.get(WALL_ENTITY_ID)
    assert state.state == HVAC_MODE_AUTO
    assert state.attributes.get(ATTR_TEMPERATURE) == 23.0
