"""The tests for the generic_thermostat, not dependant on preset/away_temp config."""
import datetime
from os import path

import pytest
import pytz
import voluptuous as vol

from homeassistant import config as hass_config
from homeassistant.components import input_boolean, switch
from homeassistant.components.climate.const import (
    ATTR_PRESET_MODE,
    DOMAIN,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_NONE,
)
from homeassistant.components.generic_thermostat import (
    DOMAIN as GENERIC_THERMOSTAT_DOMAIN,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    SERVICE_RELOAD,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
import homeassistant.core as ha
from homeassistant.core import DOMAIN as HASS_DOMAIN, CoreState, State, callback
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM

from tests.async_mock import patch
from tests.common import (
    assert_setup_component,
    async_fire_time_changed,
    mock_restore_cache,
)
from tests.components.climate import common

ENTITY = "climate.test"
ENT_SENSOR = "sensor.test"
ENT_SWITCH = "switch.test"
HEAT_ENTITY = "climate.test_heat"
COOL_ENTITY = "climate.test_cool"
ATTR_AWAY_MODE = "away_mode"
MIN_TEMP = 3.0
MAX_TEMP = 65.0
TARGET_TEMP = 42.0
COLD_TOLERANCE = 0.5
HOT_TOLERANCE = 0.5


def _setup_sensor(hass, temp):
    """Set up the test sensor."""
    hass.states.async_set(ENT_SENSOR, temp)


def _setup_switch(hass, is_on):
    """Set up the test switch."""
    hass.states.async_set(ENT_SWITCH, STATE_ON if is_on else STATE_OFF)
    calls = []

    @callback
    def log_call(call):
        """Log service calls."""
        calls.append(call)

    hass.services.async_register(ha.DOMAIN, SERVICE_TURN_ON, log_call)
    hass.services.async_register(ha.DOMAIN, SERVICE_TURN_OFF, log_call)

    return calls


async def test_setup_missing_conf(hass):
    """Test set up heat_control with missing config values."""
    config = {
        "platform": "generic_thermostat",
        "name": "test",
        "target_sensor": ENT_SENSOR,
    }
    with assert_setup_component(0):
        await async_setup_component(hass, "climate", {"climate": config})


async def test_valid_conf(hass):
    """Test set up generic_thermostat with valid config values."""
    assert await async_setup_component(
        hass,
        "climate",
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "heater": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
            }
        },
    )


@pytest.fixture
async def setup_comp_common_1(hass):
    """Initialize components."""
    hass.config.units = METRIC_SYSTEM
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()


async def test_heater_input_boolean(hass, setup_comp_common_1):
    """Test heater switching input_boolean."""
    heater_switch = "input_boolean.test"
    assert await async_setup_component(
        hass, input_boolean.DOMAIN, {"input_boolean": {"test": None}}
    )

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "heater": heater_switch,
                "target_sensor": ENT_SENSOR,
                "initial_hvac_mode": HVAC_MODE_HEAT,
            }
        },
    )
    await hass.async_block_till_done()

    assert STATE_OFF == hass.states.get(heater_switch).state

    _setup_sensor(hass, 18)
    await hass.async_block_till_done()
    await common.async_set_temperature(hass, 23)

    assert STATE_ON == hass.states.get(heater_switch).state


async def test_heater_switch(hass, setup_comp_common_1):
    """Test heater switching test switch."""
    platform = getattr(hass.components, "test.switch")
    platform.init()
    switch_1 = platform.ENTITIES[1]
    assert await async_setup_component(
        hass, switch.DOMAIN, {"switch": {"platform": "test"}}
    )
    await hass.async_block_till_done()
    heater_switch = switch_1.entity_id

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "heater": heater_switch,
                "target_sensor": ENT_SENSOR,
                "initial_hvac_mode": HVAC_MODE_HEAT,
            }
        },
    )

    await hass.async_block_till_done()
    assert STATE_OFF == hass.states.get(heater_switch).state

    _setup_sensor(hass, 18)
    await common.async_set_temperature(hass, 23)
    await hass.async_block_till_done()

    assert STATE_ON == hass.states.get(heater_switch).state


async def test_sensor_unknown(hass):
    """Test when target sensor is Unknown."""
    hass.states.async_set("sensor.unknown", STATE_UNKNOWN)
    assert await async_setup_component(
        hass,
        "climate",
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "unknown",
                "heater": ENT_SWITCH,
                "target_sensor": "sensor.unknown",
            }
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("climate.unknown")
    assert state.attributes.get("current_temperature") is None


async def test_sensor_unavailable(hass):
    """Test when target sensor is Unavailable."""
    hass.states.async_set("sensor.unavailable", STATE_UNAVAILABLE)
    assert await async_setup_component(
        hass,
        "climate",
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "unavailable",
                "heater": ENT_SWITCH,
                "target_sensor": "sensor.unavailable",
            }
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("climate.unavailable")
    assert state.attributes.get("current_temperature") is None


@pytest.fixture
async def setup_comp_common_2(hass):
    """Initialize components."""
    hass.config.temperature_unit = TEMP_CELSIUS
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "cold_tolerance": 0.3,
                "hot_tolerance": 0.3,
                "heater": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "ac_mode": True,
                "min_cycle_duration": datetime.timedelta(minutes=10),
                "initial_hvac_mode": HVAC_MODE_COOL,
            }
        },
    )
    await hass.async_block_till_done()


async def test_temp_change_ac_trigger_on_not_long_enough(hass, setup_comp_common_2):
    """Test if temperature change turn ac on."""
    calls = _setup_switch(hass, False)
    await common.async_set_temperature(hass, 25)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_temp_change_ac_trigger_on_long_enough(hass, setup_comp_common_2):
    """Test if temperature change turn ac on."""
    fake_changed = datetime.datetime(
        1918, 11, 11, 11, 11, 11, tzinfo=datetime.timezone.utc
    )
    with patch(
        "homeassistant.helpers.condition.dt_util.utcnow", return_value=fake_changed
    ):
        calls = _setup_switch(hass, False)
    await common.async_set_temperature(hass, 25)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data["entity_id"]


async def test_temp_change_ac_trigger_off_not_long_enough(hass, setup_comp_common_2):
    """Test if temperature change turn ac on."""
    calls = _setup_switch(hass, True)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_temp_change_ac_trigger_off_long_enough(hass, setup_comp_common_2):
    """Test if temperature change turn ac on."""
    fake_changed = datetime.datetime(
        1918, 11, 11, 11, 11, 11, tzinfo=datetime.timezone.utc
    )
    with patch(
        "homeassistant.helpers.condition.dt_util.utcnow", return_value=fake_changed
    ):
        calls = _setup_switch(hass, True)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data["entity_id"]


async def test_mode_change_ac_trigger_off_not_long_enough(hass, setup_comp_common_2):
    """Test if mode change turns ac off despite minimum cycle."""
    calls = _setup_switch(hass, True)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    await common.async_set_hvac_mode(hass, HVAC_MODE_OFF)
    assert 1 == len(calls)
    call = calls[0]
    assert "homeassistant" == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data["entity_id"]


async def test_mode_change_ac_trigger_on_not_long_enough(hass, setup_comp_common_2):
    """Test if mode change turns ac on despite minimum cycle."""
    calls = _setup_switch(hass, False)
    await common.async_set_temperature(hass, 25)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    await common.async_set_hvac_mode(hass, HVAC_MODE_HEAT)
    assert 1 == len(calls)
    call = calls[0]
    assert "homeassistant" == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data["entity_id"]


@pytest.fixture
async def setup_comp_common_3(hass):
    """Initialize components."""
    hass.config.temperature_unit = TEMP_CELSIUS
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "cold_tolerance": 0.3,
                "hot_tolerance": 0.3,
                "heater": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "ac_mode": True,
                "min_cycle_duration": datetime.timedelta(minutes=10),
                "initial_hvac_mode": HVAC_MODE_COOL,
            }
        },
    )
    await hass.async_block_till_done()


async def test_temp_change_ac_trigger_on_not_long_enough_2(hass, setup_comp_common_3):
    """Test if temperature change turn ac on."""
    calls = _setup_switch(hass, False)
    await common.async_set_temperature(hass, 25)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_temp_change_ac_trigger_on_long_enough_2(hass, setup_comp_common_3):
    """Test if temperature change turn ac on."""
    fake_changed = datetime.datetime(
        1918, 11, 11, 11, 11, 11, tzinfo=datetime.timezone.utc
    )
    with patch(
        "homeassistant.helpers.condition.dt_util.utcnow", return_value=fake_changed
    ):
        calls = _setup_switch(hass, False)
    await common.async_set_temperature(hass, 25)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data["entity_id"]


async def test_temp_change_ac_trigger_off_not_long_enough_2(hass, setup_comp_common_3):
    """Test if temperature change turn ac on."""
    calls = _setup_switch(hass, True)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_temp_change_ac_trigger_off_long_enough_2(hass, setup_comp_common_3):
    """Test if temperature change turn ac on."""
    fake_changed = datetime.datetime(
        1918, 11, 11, 11, 11, 11, tzinfo=datetime.timezone.utc
    )
    with patch(
        "homeassistant.helpers.condition.dt_util.utcnow", return_value=fake_changed
    ):
        calls = _setup_switch(hass, True)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data["entity_id"]


async def test_mode_change_ac_trigger_off_not_long_enough_2(hass, setup_comp_common_3):
    """Test if mode change turns ac off despite minimum cycle."""
    calls = _setup_switch(hass, True)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    await common.async_set_hvac_mode(hass, HVAC_MODE_OFF)
    assert 1 == len(calls)
    call = calls[0]
    assert "homeassistant" == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data["entity_id"]


async def test_mode_change_ac_trigger_on_not_long_enough_2(hass, setup_comp_common_3):
    """Test if mode change turns ac on despite minimum cycle."""
    calls = _setup_switch(hass, False)
    await common.async_set_temperature(hass, 25)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    await common.async_set_hvac_mode(hass, HVAC_MODE_HEAT)
    assert 1 == len(calls)
    call = calls[0]
    assert "homeassistant" == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data["entity_id"]


@pytest.fixture
async def setup_comp_common_4(hass):
    """Initialize components."""
    hass.config.temperature_unit = TEMP_CELSIUS
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "cold_tolerance": 0.3,
                "hot_tolerance": 0.3,
                "heater": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "min_cycle_duration": datetime.timedelta(minutes=10),
                "initial_hvac_mode": HVAC_MODE_HEAT,
            }
        },
    )
    await hass.async_block_till_done()


async def test_temp_change_heater_trigger_off_not_long_enough(
    hass, setup_comp_common_4
):
    """Test if temp change doesn't turn heater off because of time."""
    calls = _setup_switch(hass, True)
    await common.async_set_temperature(hass, 25)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_temp_change_heater_trigger_on_not_long_enough(hass, setup_comp_common_4):
    """Test if temp change doesn't turn heater on because of time."""
    calls = _setup_switch(hass, False)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_temp_change_heater_trigger_on_long_enough(hass, setup_comp_common_4):
    """Test if temperature change turn heater on after min cycle."""
    fake_changed = datetime.datetime(
        1918, 11, 11, 11, 11, 11, tzinfo=datetime.timezone.utc
    )
    with patch(
        "homeassistant.helpers.condition.dt_util.utcnow", return_value=fake_changed
    ):
        calls = _setup_switch(hass, False)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data["entity_id"]


async def test_temp_change_heater_trigger_off_long_enough(hass, setup_comp_common_4):
    """Test if temperature change turn heater off after min cycle."""
    fake_changed = datetime.datetime(
        1918, 11, 11, 11, 11, 11, tzinfo=datetime.timezone.utc
    )
    with patch(
        "homeassistant.helpers.condition.dt_util.utcnow", return_value=fake_changed
    ):
        calls = _setup_switch(hass, True)
    await common.async_set_temperature(hass, 25)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data["entity_id"]


async def test_mode_change_heater_trigger_off_not_long_enough(
    hass, setup_comp_common_4
):
    """Test if mode change turns heater off despite minimum cycle."""
    calls = _setup_switch(hass, True)
    await common.async_set_temperature(hass, 25)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    await common.async_set_hvac_mode(hass, HVAC_MODE_OFF)
    assert 1 == len(calls)
    call = calls[0]
    assert "homeassistant" == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data["entity_id"]


async def test_mode_change_heater_trigger_on_not_long_enough(hass, setup_comp_common_4):
    """Test if mode change turns heater on despite minimum cycle."""
    calls = _setup_switch(hass, False)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    await common.async_set_hvac_mode(hass, HVAC_MODE_HEAT)
    assert 1 == len(calls)
    call = calls[0]
    assert "homeassistant" == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data["entity_id"]


@pytest.fixture
async def setup_comp_common_5(hass):
    """Initialize components."""
    hass.config.temperature_unit = TEMP_CELSIUS
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "cold_tolerance": 0.3,
                "hot_tolerance": 0.3,
                "heater": ENT_SWITCH,
                "target_temp": 25,
                "target_sensor": ENT_SENSOR,
                "ac_mode": True,
                "min_cycle_duration": datetime.timedelta(minutes=15),
                "keep_alive": datetime.timedelta(minutes=10),
                "initial_hvac_mode": HVAC_MODE_COOL,
            }
        },
    )

    await hass.async_block_till_done()


async def test_temp_change_ac_trigger_on_long_enough_3(hass, setup_comp_common_5):
    """Test if turn on signal is sent at keep-alive intervals."""
    calls = _setup_switch(hass, True)
    await hass.async_block_till_done()
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    await common.async_set_temperature(hass, 25)
    test_time = datetime.datetime.now(pytz.UTC)
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    async_fire_time_changed(hass, test_time + datetime.timedelta(minutes=5))
    await hass.async_block_till_done()
    assert 0 == len(calls)
    async_fire_time_changed(hass, test_time + datetime.timedelta(minutes=10))
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data["entity_id"]


async def test_temp_change_ac_trigger_off_long_enough_3(hass, setup_comp_common_5):
    """Test if turn on signal is sent at keep-alive intervals."""
    calls = _setup_switch(hass, False)
    await hass.async_block_till_done()
    _setup_sensor(hass, 20)
    await hass.async_block_till_done()
    await common.async_set_temperature(hass, 25)
    test_time = datetime.datetime.now(pytz.UTC)
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    async_fire_time_changed(hass, test_time + datetime.timedelta(minutes=5))
    await hass.async_block_till_done()
    assert 0 == len(calls)
    async_fire_time_changed(hass, test_time + datetime.timedelta(minutes=10))
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data["entity_id"]


@pytest.fixture
async def setup_comp_common_6(hass):
    """Initialize components."""
    hass.config.temperature_unit = TEMP_CELSIUS
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "cold_tolerance": 0.3,
                "hot_tolerance": 0.3,
                "target_temp": 25,
                "heater": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "min_cycle_duration": datetime.timedelta(minutes=15),
                "keep_alive": datetime.timedelta(minutes=10),
                "initial_hvac_mode": HVAC_MODE_HEAT,
            }
        },
    )
    await hass.async_block_till_done()


async def test_temp_change_heater_trigger_on_long_enough_2(hass, setup_comp_common_6):
    """Test if turn on signal is sent at keep-alive intervals."""
    calls = _setup_switch(hass, True)
    await hass.async_block_till_done()
    _setup_sensor(hass, 20)
    await hass.async_block_till_done()
    await common.async_set_temperature(hass, 25)
    test_time = datetime.datetime.now(pytz.UTC)
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    async_fire_time_changed(hass, test_time + datetime.timedelta(minutes=5))
    await hass.async_block_till_done()
    assert 0 == len(calls)
    async_fire_time_changed(hass, test_time + datetime.timedelta(minutes=10))
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_ON == call.service
    assert ENT_SWITCH == call.data["entity_id"]


async def test_temp_change_heater_trigger_off_long_enough_2(hass, setup_comp_common_6):
    """Test if turn on signal is sent at keep-alive intervals."""
    calls = _setup_switch(hass, False)
    await hass.async_block_till_done()
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    await common.async_set_temperature(hass, 25)
    test_time = datetime.datetime.now(pytz.UTC)
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done()
    assert 0 == len(calls)
    async_fire_time_changed(hass, test_time + datetime.timedelta(minutes=5))
    await hass.async_block_till_done()
    assert 0 == len(calls)
    async_fire_time_changed(hass, test_time + datetime.timedelta(minutes=10))
    await hass.async_block_till_done()
    assert 1 == len(calls)
    call = calls[0]
    assert HASS_DOMAIN == call.domain
    assert SERVICE_TURN_OFF == call.service
    assert ENT_SWITCH == call.data["entity_id"]


@pytest.fixture
async def setup_comp_common_7(hass):
    """Initialize components."""
    hass.config.temperature_unit = TEMP_FAHRENHEIT
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "cold_tolerance": 0.3,
                "hot_tolerance": 0.3,
                "target_temp": 25,
                "heater": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "min_cycle_duration": datetime.timedelta(minutes=15),
                "keep_alive": datetime.timedelta(minutes=10),
                "precision": 0.1,
            }
        },
    )
    await hass.async_block_till_done()


async def test_precision(hass, setup_comp_common_7):
    """Test that setting precision to tenths works as intended."""
    await common.async_set_temperature(hass, 23.27)
    state = hass.states.get(ENTITY)
    assert 23.3 == state.attributes.get("temperature")


async def test_custom_setup_params(hass):
    """Test the setup with custom parameters."""
    result = await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "heater": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "min_temp": MIN_TEMP,
                "max_temp": MAX_TEMP,
                "target_temp": TARGET_TEMP,
            }
        },
    )
    assert result
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY)
    assert state.attributes.get("min_temp") == MIN_TEMP
    assert state.attributes.get("max_temp") == MAX_TEMP
    assert state.attributes.get("temperature") == TARGET_TEMP


async def test_reload(hass):
    """Test we can reload."""

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "heater": "switch.any",
                "target_sensor": "sensor.any",
            }
        },
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1
    assert hass.states.get("climate.test") is not None

    yaml_path = path.join(
        _get_fixtures_base_path(),
        "fixtures",
        "generic_thermostat/configuration.yaml",
    )
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            GENERIC_THERMOSTAT_DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert hass.states.get("climate.test") is None
    assert hass.states.get("climate.reload")


def _get_fixtures_base_path():
    return path.dirname(path.dirname(path.dirname(__file__)))
