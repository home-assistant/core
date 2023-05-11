"""The test for the pid_controller number platform."""
import asyncio
import logging
from unittest.mock import patch

import pytest

from homeassistant import config as hass_config
from homeassistant.components.number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.components.pid_controller.const import (
    CONF_CYCLE_TIME,
    CONF_INPUT1,
    CONF_INPUT2,
    CONF_OUTPUT,
    CONF_PID_DIR,
    CONF_PID_KD,
    CONF_PID_KI,
    CONF_PID_KP,
    DOMAIN,
    PID_DIR_REVERSE,
    SERVICE_ENABLE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_NAME,
    CONF_PLATFORM,
    SERVICE_RELOAD,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM

from tests.common import get_fixture_path

_LOGGER = logging.getLogger(__name__)


@pytest.fixture(name="setup_comp")
async def fixture_setup_comp(hass):
    """Initialize components."""
    hass.config.units = METRIC_SYSTEM
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()


async def _setup_controller(hass, config, input, output, input_value, output_value):
    """Setupfunctions for the controller.

    The input and output device do really exist, only set state.
    """
    hass.states.async_set(input, input_value)
    if output:
        hass.states.async_set(output, output_value)
    assert await async_setup_component(hass, Platform.NUMBER, config)
    await hass.async_block_till_done()


async def test_pid_controller_kp(hass: HomeAssistant, setup_comp) -> None:
    """Test function Kp for normal pid controller (number): output should equal error."""
    input = "sensor.input1"
    output = "number.output"
    pid = f"{Platform.NUMBER}.pid"

    cycle_time = 0.01  # Cycle time in seconds
    config = {
        Platform.NUMBER: {
            CONF_PLATFORM: DOMAIN,
            CONF_NAME: "pid",
            CONF_INPUT1: input,
            CONF_OUTPUT: output,
            CONF_PID_KP: 1,
            CONF_PID_KI: 0,
            CONF_PID_KD: 0,
            CONF_CYCLE_TIME: {"seconds": cycle_time},
        }
    }
    await _setup_controller(hass, config, input, output, 10.0, 0.0)

    # On initialize value is 0, so output should be off. Check all states.
    assert hass.states.get(pid).state == "0.0"
    assert hass.states.get(input).state == "10.0"
    assert hass.states.get(output).state == "0.0"

    # Now set pid setpoint to value 20. Input remains 10, but pid is not yet enabled,
    # so output state should remain 0.
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 20, ATTR_ENTITY_ID: pid},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(pid).state == "20.0"
    assert hass.states.get(output).state == "0.0"

    # Enable PID controller. Output should run up after a while to 10
    assert await hass.services.async_call(
        "pid_controller",
        SERVICE_ENABLE,
        {ATTR_VALUE: True, ATTR_ENTITY_ID: pid},
        blocking=True,
    )
    await hass.async_block_till_done()
    # Sleep some cyles.
    await asyncio.sleep(cycle_time * 3)
    # Check if output is equal to 10, as Kp=1
    # and difference between in- and output is 10.
    assert hass.states.get(output).state == "10.0"
    assert await hass.services.async_call(
        "homeassistant",
        "stop",
        None,
        blocking=True,
    )


async def test_pid_controller_kp_reverse(hass: HomeAssistant, setup_comp) -> None:
    """Test function Kp for normal pid controller (number): output should equal error."""
    input = "sensor.input1"
    output = "number.output"
    pid = f"{Platform.NUMBER}.pid"

    # Min/max of the controller are set up by output limits, so assign
    hass.states.async_set(output, 0.0)
    state = hass.states.get(output)
    attr = state.attributes.copy()
    attr["min"] = -100.0
    attr["max"] = 100.0
    hass.states.async_set(output, 0.0, attr)

    cycle_time = 0.01  # Cycle time in seconds
    config = {
        Platform.NUMBER: {
            CONF_PLATFORM: DOMAIN,
            CONF_NAME: "pid",
            CONF_INPUT1: input,
            CONF_OUTPUT: output,
            CONF_PID_KP: 1,
            CONF_PID_KI: 0,
            CONF_PID_KD: 0,
            CONF_PID_DIR: PID_DIR_REVERSE,
            CONF_CYCLE_TIME: {"seconds": cycle_time},
        }
    }
    await _setup_controller(hass, config, input, None, 10.0, 0.0)

    # On initialize value is 0, so output should be off. Check all states.
    assert hass.states.get(pid).state == "0.0"
    assert hass.states.get(input).state == "10.0"
    assert hass.states.get(output).state == "0.0"

    # Now set pid setpoint to value 20. Input remains 10, but pid is not yet enabled,
    # so output state should remain 0.
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 20, ATTR_ENTITY_ID: pid},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(pid).state == "20.0"
    assert hass.states.get(output).state == "0.0"

    # Enable PID controller. Output should run down after a while to -10
    assert await hass.services.async_call(
        "pid_controller",
        SERVICE_ENABLE,
        {ATTR_VALUE: True, ATTR_ENTITY_ID: pid},
        blocking=True,
    )
    await hass.async_block_till_done()
    # Sleep some cyles.
    await asyncio.sleep(cycle_time * 3)
    # Check if output is equal to -10, as Kp=1
    # and difference between in- and output is 10.
    assert hass.states.get(output).state == "-10.0"
    # Now invert in- and output; output state should
    # change polarity.
    # Set pid setpoint to value 10.
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 10, ATTR_ENTITY_ID: pid},
        blocking=True,
    )
    # Set input to value 20
    hass.states.async_set(input, 20.0)
    # Sleep some cyles.
    await asyncio.sleep(cycle_time * 3)
    # Check if output is equal to 10, as Kp=1
    # and difference between in- and output is -10.
    assert hass.states.get(output).state == "10.0"

    assert await hass.services.async_call(
        "homeassistant",
        "stop",
        None,
        blocking=True,
    )


async def test_pid_controller_kp_differential(hass: HomeAssistant, setup_comp) -> None:
    """Test function Kp for normal pid controller (number): output should equal error."""
    input = "sensor.input1"
    input2 = "sensor.input2"
    output = "number.output"
    pid = f"{Platform.NUMBER}.pid"

    cycle_time = 0.01  # Cycle time in seconds
    config = {
        Platform.NUMBER: {
            CONF_PLATFORM: DOMAIN,
            CONF_NAME: "pid",
            CONF_INPUT1: input,
            CONF_INPUT2: input2,
            CONF_OUTPUT: output,
            CONF_PID_KP: 1,
            CONF_PID_KI: 0,
            CONF_PID_KD: 0,
            CONF_CYCLE_TIME: {"seconds": cycle_time},
        }
    }
    await _setup_controller(hass, config, input, output, 10.0, 0.0)
    # Assign input2 value
    hass.states.async_set(input2, 12.0)

    # On initialize value is 0, so output should be off. Check all states.
    assert hass.states.get(pid).state == "0.0"
    assert hass.states.get(input).state == "10.0"
    assert hass.states.get(input2).state == "12.0"
    assert hass.states.get(output).state == "0.0"

    # Now set pid setpoint to value 20. Input remains 10, but pid is not yet enabled,
    # so output state should remain 0.
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 20, ATTR_ENTITY_ID: pid},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(pid).state == "20.0"
    assert hass.states.get(output).state == "0.0"

    # Enable PID controller. Output should run down after a while to -10
    assert await hass.services.async_call(
        "pid_controller",
        SERVICE_ENABLE,
        {ATTR_VALUE: True, ATTR_ENTITY_ID: pid},
        blocking=True,
    )
    await hass.async_block_till_done()
    # Sleep some cyles.
    await asyncio.sleep(cycle_time * 3)
    # Check if output is equal to 2, as Kp=1
    # and difference between in- two inputs is 2.
    assert hass.states.get(output).state == "18.0"
    assert await hass.services.async_call(
        "homeassistant",
        "stop",
        None,
        blocking=True,
    )


async def test_pid_controller_ki(hass: HomeAssistant, setup_comp) -> None:
    """Test Ki function for normal pid controller (number): output should run to max."""
    input = "sensor.input1"
    output = "number.output"
    pid = f"{Platform.NUMBER}.pid"
    cycle_time = 0.01  # Cycle time in seconds

    config = {
        Platform.NUMBER: {
            CONF_PLATFORM: DOMAIN,
            CONF_NAME: "pid",
            CONF_INPUT1: input,
            CONF_OUTPUT: output,
            CONF_PID_KP: 0,
            CONF_PID_KI: 100,
            CONF_PID_KD: 0,
            CONF_CYCLE_TIME: {"seconds": cycle_time},
        }
    }
    await _setup_controller(hass, config, input, output, 10.0, 0.0)

    # On initialize value is 0, so output should be off. Check all states.
    assert hass.states.get(pid).state == "0.0"
    assert hass.states.get(input).state == "10.0"
    assert hass.states.get(output).state == "0.0"

    # Now set pid setpoint to value 20. Input remains 10, but pid is not yet enabled,
    # so output state should remain 0.
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 20, ATTR_ENTITY_ID: pid},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(pid).state == "20.0"
    assert hass.states.get(output).state == "0.0"

    # Enable PID controller. Output should run up after a while to 100
    # (as that's the max of the output)
    assert await hass.services.async_call(
        "pid_controller",
        SERVICE_ENABLE,
        {ATTR_VALUE: True, ATTR_ENTITY_ID: pid},
        blocking=True,
    )
    await hass.async_block_till_done()
    # Sleep some cyles.
    await asyncio.sleep(cycle_time * 10)
    # Check if output is equal to 100, as Ki=100
    # and difference between in- and output is 10.
    assert hass.states.get(output).state == "100.0"
    assert await hass.services.async_call(
        "homeassistant",
        "stop",
        None,
        blocking=True,
    )


async def test_pid_controller_kd(hass: HomeAssistant, setup_comp) -> None:
    """Test Kd function for normal pid controller (number): output should stay 0."""
    input = "sensor.input1"
    output = "number.output"
    pid = f"{Platform.NUMBER}.pid"
    cycle_time = 0.01  # Cycle time in seconds

    config = {
        Platform.NUMBER: {
            CONF_PLATFORM: DOMAIN,
            CONF_NAME: "pid",
            CONF_INPUT1: input,
            CONF_OUTPUT: output,
            CONF_PID_KP: 0,
            CONF_PID_KI: 0,
            CONF_PID_KD: 100,
            CONF_CYCLE_TIME: {"seconds": cycle_time},
        }
    }
    await _setup_controller(hass, config, input, output, 10.0, 0.0)

    # On initialize value is 0, so output should be off. Check all states.
    assert hass.states.get(pid).state == "0.0"
    assert hass.states.get(input).state == "10.0"
    assert hass.states.get(output).state == "0.0"

    # Now set pid setpoint to value 20. Input remains 10, but pid is not yet enabled,
    # so output state should remain 0.
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 20, ATTR_ENTITY_ID: pid},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(pid).state == "20.0"
    assert hass.states.get(output).state == "0.0"

    # Enable PID controller. Output should run up after a while to 100
    # (as that's the max of the output)
    assert await hass.services.async_call(
        "pid_controller",
        SERVICE_ENABLE,
        {ATTR_VALUE: True, ATTR_ENTITY_ID: pid},
        blocking=True,
    )
    await hass.async_block_till_done()
    # Sleep some cyles.
    await asyncio.sleep(cycle_time * 10)
    # Check if output is equal to 0, as we only have a Kd100
    # and  input remains always 10.0
    assert hass.states.get(output).state == "0.0"
    assert await hass.services.async_call(
        "homeassistant",
        "stop",
        None,
        blocking=True,
    )


async def test_output_does_not_exist(hass: HomeAssistant, setup_comp, caplog) -> None:
    """Test output does not exist."""
    input = "sensor.input1"
    output = "number.output"
    cycle_time = 0.01  # Cycle time in seconds

    # clear logging
    caplog.clear()
    config = {
        Platform.NUMBER: {
            CONF_PLATFORM: DOMAIN,
            CONF_NAME: "pid",
            CONF_INPUT1: input,
            CONF_OUTPUT: "DoesNotExist",
            CONF_PID_KP: 1,
            CONF_PID_KI: 0,
            CONF_PID_KD: 0,
            CONF_CYCLE_TIME: {"seconds": cycle_time},
        }
    }
    await _setup_controller(hass, config, input, output, 10.0, 0.0)

    # test if an error was generated
    assert "ERROR" in caplog.text
    assert await hass.services.async_call(
        "homeassistant",
        "stop",
        None,
        blocking=True,
    )


async def test_outside_range(hass: HomeAssistant, setup_comp) -> None:
    """Test what happens if we write a value outside the range."""
    input = "sensor.input1"
    output = "number.output"
    pid = f"{Platform.NUMBER}.pid"
    cycle_time = 0.01  # Cycle time in seconds
    minimum = 20.0
    maximum = 30.0

    config = {
        Platform.NUMBER: {
            CONF_PLATFORM: DOMAIN,
            CONF_NAME: "pid",
            CONF_INPUT1: input,
            CONF_OUTPUT: output,
            CONF_PID_KP: 1,
            CONF_PID_KI: 0,
            CONF_PID_KD: 0,
            CONF_CYCLE_TIME: {"seconds": cycle_time},
            CONF_MINIMUM: minimum,
            CONF_MAXIMUM: maximum,
        }
    }
    await _setup_controller(hass, config, input, output, 10.0, 0.0)

    # On initialize value is 0, so output should be off. Check all states.
    assert hass.states.get(pid).state == "20.0"
    assert hass.states.get(input).state == "10.0"
    assert hass.states.get(output).state == "0.0"

    # Set value to 5. This should generate a ValueError in the number component
    with pytest.raises(Exception):
        await hass.services.async_call(
            Platform.NUMBER,
            SERVICE_SET_VALUE,
            {ATTR_VALUE: 5, ATTR_ENTITY_ID: pid},
            blocking=True,
        )

    await hass.async_block_till_done()
    # Value should not be changed
    assert hass.states.get(pid).state == "20.0"
    assert hass.states.get(output).state == "0.0"

    # Set value to 50. This should generate a ValueError in the number component
    with pytest.raises(Exception):
        await hass.services.async_call(
            Platform.NUMBER,
            SERVICE_SET_VALUE,
            {ATTR_VALUE: 50, ATTR_ENTITY_ID: pid},
            blocking=True,
        )

    await hass.async_block_till_done()
    # Value should not be changed
    assert hass.states.get(pid).state == "20.0"
    assert hass.states.get(output).state == "0.0"

    # Enable PID controller and repeat
    assert await hass.services.async_call(
        "pid_controller",
        SERVICE_ENABLE,
        {ATTR_VALUE: True, ATTR_ENTITY_ID: pid},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Set value to 5. This should generate a ValueError in the number component
    with pytest.raises(Exception):
        await hass.services.async_call(
            Platform.NUMBER,
            SERVICE_SET_VALUE,
            {ATTR_VALUE: 5, ATTR_ENTITY_ID: pid},
            blocking=True,
        )
    await hass.async_block_till_done()
    await asyncio.sleep(cycle_time * 3)
    # Value should not be changed, except output should regulate to 10 now.
    assert hass.states.get(pid).state == "20.0"
    assert hass.states.get(output).state == "10.0"

    # Set value to 50. This should generate a ValueError in the number component
    with pytest.raises(Exception):
        await hass.services.async_call(
            Platform.NUMBER,
            SERVICE_SET_VALUE,
            {ATTR_VALUE: 50, ATTR_ENTITY_ID: pid},
            blocking=True,
        )

    await hass.async_block_till_done()
    await asyncio.sleep(cycle_time * 3)
    # Value should not be changed, except output still regulated to 10 now.
    assert hass.states.get(pid).state == "20.0"
    assert hass.states.get(output).state == "10.0"
    # Stop hass
    assert await hass.services.async_call(
        "homeassistant",
        "stop",
        None,
        blocking=True,
    )


async def test_bad_value(hass: HomeAssistant, setup_comp, caplog) -> None:
    """Test what happens if we send a bad value."""
    input = "sensor.input1"
    output = "number.output"
    pid = f"{Platform.NUMBER}.pid"
    cycle_time = 0.01  # Cycle time in seconds

    config = {
        Platform.NUMBER: {
            CONF_PLATFORM: DOMAIN,
            CONF_NAME: "pid",
            CONF_INPUT1: input,
            CONF_OUTPUT: output,
            CONF_PID_KP: 1,
            CONF_PID_KI: 0,
            CONF_PID_KD: 0,
            CONF_CYCLE_TIME: {"seconds": cycle_time},
        }
    }
    await _setup_controller(hass, config, input, output, 10.0, 0.0)

    # On initialize value is 0, so output should be off. Check all states.
    assert hass.states.get(pid).state == "0.0"
    assert hass.states.get(input).state == "10.0"
    assert hass.states.get(output).state == "0.0"

    # Set value to "infinity". This should generate an exception, value should remain what it was
    with pytest.raises(Exception):
        await hass.services.async_call(
            Platform.NUMBER,
            SERVICE_SET_VALUE,
            {ATTR_VALUE: "inf", ATTR_ENTITY_ID: pid},
            blocking=True,
        )
    assert hass.states.get(pid).state == "0.0"

    # Set value to "nan". This should generate a warning, value should remain what it was
    caplog.clear()
    await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: "nan", ATTR_ENTITY_ID: pid},
        blocking=True,
    )
    assert hass.states.get(pid).state == "0.0"
    # test if a warning was generated
    assert "WARNING" in caplog.text

    # Now repeat with controller enabled
    # Enable PID controller and repeat
    assert await hass.services.async_call(
        "pid_controller",
        SERVICE_ENABLE,
        {ATTR_VALUE: True, ATTR_ENTITY_ID: pid},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Set value to "infinity". This should generate an exception, value should remain what it was
    with pytest.raises(Exception):
        await hass.services.async_call(
            Platform.NUMBER,
            SERVICE_SET_VALUE,
            {ATTR_VALUE: "inf", ATTR_ENTITY_ID: pid},
            blocking=True,
        )
    assert hass.states.get(pid).state == "0.0"

    # Set value to "nan". This should generate a warning, value should remain what it was
    caplog.clear()
    await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: "nan", ATTR_ENTITY_ID: pid},
        blocking=True,
    )
    assert hass.states.get(pid).state == "0.0"

    assert await hass.services.async_call(
        "homeassistant",
        "stop",
        None,
        blocking=True,
    )


async def test_reload(hass: HomeAssistant, setup_comp) -> None:
    """Verify we can reload pid_controller from yaml file."""
    input = "sensor.input1"
    output = "number.output"
    pid = f"{Platform.NUMBER}.pid"
    cycle_time = 0.01  # Cycle time in seconds

    config = {
        Platform.NUMBER: {
            CONF_PLATFORM: DOMAIN,
            CONF_NAME: "pid",
            CONF_INPUT1: input,
            CONF_OUTPUT: output,
            CONF_PID_KP: 1,
            CONF_PID_KI: 0,
            CONF_PID_KD: 0,
            CONF_CYCLE_TIME: {"seconds": cycle_time},
        }
    }
    await _setup_controller(hass, config, input, output, 10.0, 0.0)

    # On initialize value is 0, so output should be off. Check all states.
    assert hass.states.get(pid).state == "0.0"
    assert hass.states.get(input).state == "10.0"
    assert hass.states.get(output).state == "0.0"
    assert len(hass.states.async_all()) == 3

    yaml_path = get_fixture_path("configuration.yaml", "pid_controller")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 3
    assert hass.states.get(pid) is None
    assert hass.states.get("number.second_test")
