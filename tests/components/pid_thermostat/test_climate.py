"""The tests for the PID_thermostat climate component."""

import asyncio
import logging

import pytest
import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.pid_controller.const import (
    CONF_CYCLE_TIME,
    CONF_PID_KD,
    CONF_PID_KI,
    CONF_PID_KP,
)
from homeassistant.components.pid_thermostat.const import (
    AC_MODE_COOL,
    AC_MODE_HEAT,
    CONF_AC_MODE,
    CONF_HEATER,
    CONF_SENSOR,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.components.slow_pwm.const import CONF_OUTPUTS
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_PLATFORM,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM

from tests.common import async_mock_service
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401

LOGGER = logging.getLogger(__name__)


ENTITY_CLIMATE = "climate.pid_thermostat"
ENTITY_SENSOR = "sensor.temperature"
ENTITY_HEATER = "number.heater"
CYCLE_TIME = 0.01

CLIMATE_CONFIG = {
    Platform.CLIMATE: {
        CONF_PLATFORM: DOMAIN,
        CONF_NAME: DEFAULT_NAME,
        CONF_SENSOR: ENTITY_SENSOR,
        CONF_HEATER: ENTITY_HEATER,
        CONF_CYCLE_TIME: {"seconds": CYCLE_TIME},
    }
}

NUMBER_CONFIG = {
    Platform.NUMBER: {
        CONF_PLATFORM: "slow_pwm",
        CONF_NAME: "heater",
        CONF_OUTPUTS: ["switch.heater"],
    }
}


@pytest.fixture(autouse=True)
async def setup_helpers(hass):
    """Initialize hass and helper components."""
    hass.config.units = METRIC_SYSTEM
    hass.states.async_set(ENTITY_SENSOR, 10.0)
    # Mock on/off switching for slow_pwm component component
    async_mock_service(hass, "homeassistant", "turn_on")
    async_mock_service(hass, "homeassistant", "turn_off")
    # Create a number, required by the climate component first
    assert await async_setup_component(hass, Platform.NUMBER, NUMBER_CONFIG)


async def _setup_pid_climate(hass, config):
    """Setupfunctions for the pid thermostat."""
    assert await async_setup_component(hass, Platform.CLIMATE, config)
    await hass.async_block_till_done()


async def test_setup_params(hass: HomeAssistant) -> None:
    """Test the initial parameters."""
    await _setup_pid_climate(hass, CLIMATE_CONFIG)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVACMode.OFF
    assert state.attributes.get(ATTR_TEMPERATURE) == 19.0
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 10.0
    assert state.attributes.get(ATTR_HVAC_MODES) == [
        HVACMode.OFF,
        HVACMode.HEAT,
    ]


async def test_default_setup_params(hass: HomeAssistant) -> None:
    """Test the setup with default parameters."""
    await _setup_pid_climate(hass, CLIMATE_CONFIG)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_MIN_TEMP) == 7
    assert state.attributes.get(ATTR_MAX_TEMP) == 35


async def test_set_only_target_temp_bad_attr(hass: HomeAssistant) -> None:
    """Test setting the target temperature without required attribute."""
    await _setup_pid_climate(hass, CLIMATE_CONFIG)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_TEMPERATURE) == 19.0

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            Platform.CLIMATE,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_CLIMATE, ATTR_TEMPERATURE: None},
            blocking=True,
        )

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_TEMPERATURE) == 19.0


async def test_set_only_target_temp(hass: HomeAssistant) -> None:
    """Test the setting of the target temperature."""
    await _setup_pid_climate(hass, CLIMATE_CONFIG)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_TEMPERATURE) == 19.0

    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_CLIMATE, ATTR_TEMPERATURE: 30},
        blocking=True,
    )
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get(ATTR_TEMPERATURE) == 30.0
    # Range is not supported as we regulate to a temperature, should be None
    assert state.attributes.get(ATTR_TARGET_TEMP_LOW) is None
    assert state.attributes.get(ATTR_TARGET_TEMP_HIGH) is None


async def test_turn_on_and_off(hass: HomeAssistant) -> None:
    """Test turn on- and off device."""
    await _setup_pid_climate(hass, CLIMATE_CONFIG)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVACMode.OFF

    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_CLIMATE, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVACMode.OFF

    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_CLIMATE},
        blocking=True,
    )
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVACMode.HEAT

    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_CLIMATE},
        blocking=True,
    )
    await hass.async_block_till_done()
    # Sleep some cyles. Set all off and to 0 to prevent from lingering errors.
    await asyncio.sleep(CYCLE_TIME * 10)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVACMode.OFF


async def test_enable_heater_kp(hass: HomeAssistant) -> None:
    """Test enabling the thermostat, it should enable the heater. This test will check kp setting."""
    cl = CLIMATE_CONFIG.copy()
    # Inject PID values
    cl[Platform.CLIMATE][CONF_PID_KP] = 1.0
    cl[Platform.CLIMATE][CONF_PID_KI] = 0.0
    cl[Platform.CLIMATE][CONF_PID_KD] = 0.0

    await _setup_pid_climate(hass, cl)
    state = hass.states.get(ENTITY_CLIMATE)
    # Make sure input sensor is at 10 degC,
    # target temperature is at 19 degC,
    # so output should be 9 when Kp is 1.
    assert state.attributes.get(ATTR_TEMPERATURE) == 19
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 10
    assert state.state == HVACMode.OFF

    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_CLIMATE, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVACMode.HEAT

    # Sleep some cyles.
    await asyncio.sleep(CYCLE_TIME * 3)
    assert hass.states.get(ENTITY_HEATER).state == "9.0"

    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_CLIMATE, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    await hass.async_block_till_done()
    # Sleep some cyles. Set all off and to 0 to prevent from lingering errors.
    await asyncio.sleep(CYCLE_TIME * 10)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVACMode.OFF
    assert hass.states.get(ENTITY_HEATER).state == "0.0"


async def test_enable_cooler_kp(hass: HomeAssistant) -> None:
    """Test enabling the thermostat, it should enable the cooler. This test will check kp setting."""
    cl = CLIMATE_CONFIG.copy()
    # Inject PID values
    cl[Platform.CLIMATE][CONF_PID_KP] = 2.0
    cl[Platform.CLIMATE][CONF_PID_KI] = 0.0
    cl[Platform.CLIMATE][CONF_PID_KD] = 0.0
    cl[Platform.CLIMATE][CONF_AC_MODE] = AC_MODE_COOL

    await _setup_pid_climate(hass, cl)
    state = hass.states.get(ENTITY_CLIMATE)
    # Set input sensor to 25 degC,
    # target temperature is 19 degC,
    # so output should be 12 when Kp is 2.
    hass.states.async_set(ENTITY_SENSOR, 25.0)

    assert state.state == HVACMode.OFF
    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_CLIMATE, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()
    # Sleep some cyles.
    await asyncio.sleep(CYCLE_TIME * 3)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVACMode.HEAT
    assert hass.states.get(ENTITY_HEATER).state == "12.0"
    assert state.attributes.get(ATTR_TEMPERATURE) == 19
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 25
    # Switch to off again to disable the internal timers
    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_CLIMATE, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    # Sleep some cyles. Set all off and to 0 to prevent from lingering errors.
    await asyncio.sleep(CYCLE_TIME * 10)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVACMode.OFF
    assert hass.states.get(ENTITY_HEATER).state == "0.0"


async def test_enable_heater_ki(hass: HomeAssistant) -> None:
    """Test enabling the thermostat, it should enable the heater. This test will check ki setting."""
    cl = CLIMATE_CONFIG.copy()
    # Inject PID values
    cl[Platform.CLIMATE][CONF_PID_KP] = 0.0
    cl[Platform.CLIMATE][CONF_PID_KI] = 100.0
    cl[Platform.CLIMATE][CONF_PID_KD] = 0.0
    cl[Platform.CLIMATE][CONF_AC_MODE] = AC_MODE_HEAT

    await _setup_pid_climate(hass, cl)
    state = hass.states.get(ENTITY_CLIMATE)
    # Input sensor is 10 degC,
    # target temperature is 19 degC,
    # so output should clip to 100 when Kp is 2.

    assert state.state == HVACMode.OFF
    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_CLIMATE, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()
    # Sleep some cyles.
    await asyncio.sleep(CYCLE_TIME * 30)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVACMode.HEAT
    assert state.attributes.get(ATTR_TEMPERATURE) == 19
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 10
    assert hass.states.get(ENTITY_HEATER).state == "100.0"
    # Switch to off again to disable the internal timers
    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_CLIMATE, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    # Sleep some cyles. Set all off and to 0 to prevent from lingering errors.
    await asyncio.sleep(CYCLE_TIME * 10)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVACMode.OFF
    assert hass.states.get(ENTITY_HEATER).state == "0.0"


async def test_enable_heater_kd(hass: HomeAssistant) -> None:
    """Test enabling the thermostat, it should enable the heater. This test will check kd setting."""
    cl = CLIMATE_CONFIG.copy()
    # Inject PID values
    cl[Platform.CLIMATE][CONF_PID_KP] = 0.0
    cl[Platform.CLIMATE][CONF_PID_KI] = 0.0
    cl[Platform.CLIMATE][CONF_PID_KD] = 100.0
    cl[Platform.CLIMATE][CONF_AC_MODE] = AC_MODE_HEAT

    await _setup_pid_climate(hass, cl)
    state = hass.states.get(ENTITY_CLIMATE)
    # Input sensor is 10 degC,
    # target temperature is 19 degC,
    # so output should clip to 100 when Kp is 2.

    assert state.state == HVACMode.OFF
    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_CLIMATE, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()
    # Sleep some cyles.
    await asyncio.sleep(CYCLE_TIME * 30)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVACMode.HEAT
    assert state.attributes.get(ATTR_TEMPERATURE) == 19
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 10
    # Check if output is equal to 0, as we only have a Kd100
    # and  input remains always 10.0
    assert hass.states.get(ENTITY_HEATER).state == "0.0"
    # Switch to off again to disable the internal timers
    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_CLIMATE, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    # Sleep some cyles. Set all off and to 0 to prevent from lingering errors.
    await asyncio.sleep(CYCLE_TIME * 10)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == HVACMode.OFF
    assert hass.states.get(ENTITY_HEATER).state == "0.0"
