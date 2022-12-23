"""The test for the slow_pwm number platform."""
import asyncio
import logging
from unittest.mock import patch

import pytest

from homeassistant import config as hass_config
from homeassistant.components import input_boolean, switch
from homeassistant.components.number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.components.slow_pwm.const import (
    CONF_CYCLE_TIME,
    CONF_MIN_SWITCH_TIME,
    CONF_OUTPUTS,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_NAME,
    CONF_PLATFORM,
    SERVICE_RELOAD,
    STATE_OFF,
    STATE_ON,
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


async def test_single_input_boolean(hass: HomeAssistant, setup_comp) -> None:
    """Test functions for single-output slow-pwm."""
    output_switch = "input_boolean.test"
    slow_pwm = f"{Platform.NUMBER}.test"
    cycle_time = 4  # Cycle time in seconds
    assert await async_setup_component(
        hass, input_boolean.DOMAIN, {"input_boolean": {"test": None}}
    )

    assert await async_setup_component(
        hass,
        Platform.NUMBER,
        {
            Platform.NUMBER: {
                CONF_PLATFORM: DOMAIN,
                CONF_NAME: "test",
                CONF_OUTPUTS: [output_switch],
                CONF_CYCLE_TIME: {"seconds": cycle_time},
            }
        },
    )
    await hass.async_block_till_done()

    # On initialize value is 0, so output should be off
    assert hass.states.get(slow_pwm).state == "0.0"
    assert hass.states.get(output_switch).state == STATE_OFF

    # Now set value to 100%, see if output goes on
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 100, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(slow_pwm).state == "100.0"
    assert hass.states.get(output_switch).state == STATE_ON

    # Now set value to 50%. Direct after, output should be on.
    # After 1/2*cylce_time output should be off
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 50, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(slow_pwm).state == "50.0"
    assert hass.states.get(output_switch).state == STATE_ON
    await asyncio.sleep(cycle_time * 0.6)
    assert hass.states.get(output_switch).state == STATE_OFF
    # Set value to 0 to stop lingering times before we return
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 0, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )


async def test_single_switch(
    hass: HomeAssistant, setup_comp, enable_custom_integrations
) -> None:
    """Test functions for single-output slow-pwm."""
    platform = getattr(hass.components, "test.switch")
    platform.init()
    switch_1 = platform.ENTITIES[1]
    assert await async_setup_component(
        hass, switch.DOMAIN, {"switch": {"platform": "test"}}
    )
    await hass.async_block_till_done()

    output_switch = switch_1.entity_id
    _LOGGER.info("Output switch id: " + output_switch)
    slow_pwm = f"{Platform.NUMBER}.test"

    assert await async_setup_component(
        hass,
        Platform.NUMBER,
        {
            Platform.NUMBER: {
                CONF_PLATFORM: DOMAIN,
                CONF_NAME: "test",
                CONF_OUTPUTS: [output_switch],
            }
        },
    )
    await hass.async_block_till_done()

    # On initialize value is 0, so output should be off
    assert hass.states.get(slow_pwm).state == "0.0"
    assert hass.states.get(output_switch).state == STATE_OFF

    # Now set value to 100%, see if output goes on
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 100, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(slow_pwm).state == "100.0"
    assert hass.states.get(output_switch).state == STATE_ON
    # Set value to 0 to stop lingering times before we return
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 0, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )


async def test_multi_output(hass: HomeAssistant, setup_comp) -> None:
    """Test functions for multi-output slow-pwm."""
    output_switches = ["input_boolean.test1", "input_boolean.test2"]
    slow_pwm = f"{Platform.NUMBER}.test"
    assert await async_setup_component(
        hass, input_boolean.DOMAIN, {"input_boolean": {"test1": None, "test2": None}}
    )

    assert await async_setup_component(
        hass,
        Platform.NUMBER,
        {
            Platform.NUMBER: {
                CONF_PLATFORM: DOMAIN,
                CONF_NAME: "test",
                CONF_OUTPUTS: output_switches,
            }
        },
    )
    await hass.async_block_till_done()

    # On initialize value is 0, so output should be off
    assert hass.states.get(slow_pwm).state == "0.0"
    assert hass.states.get(output_switches[0]).state == STATE_OFF
    assert hass.states.get(output_switches[1]).state == STATE_OFF

    # Now set value to 50%, see if one output goes on
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 50, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(slow_pwm).state == "50.0"
    assert hass.states.get(output_switches[0]).state == STATE_ON
    assert hass.states.get(output_switches[1]).state == STATE_OFF

    # Now set value to 100%, see if both output go on
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 100, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(slow_pwm).state == "100.0"
    assert hass.states.get(output_switches[0]).state == STATE_ON
    assert hass.states.get(output_switches[1]).state == STATE_ON
    # Set value to 0 to stop lingering times before we return
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 0, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )


async def test_change_during_cycle(hass: HomeAssistant, setup_comp) -> None:
    """Test if we change value during the cycle."""
    output_switch = "input_boolean.test"
    slow_pwm = f"{Platform.NUMBER}.test"
    cycle_time = 10  # Cycle time in seconds

    assert await async_setup_component(
        hass, input_boolean.DOMAIN, {"input_boolean": {"test": None}}
    )

    assert await async_setup_component(
        hass,
        Platform.NUMBER,
        {
            Platform.NUMBER: {
                CONF_PLATFORM: DOMAIN,
                CONF_NAME: "test",
                CONF_OUTPUTS: [output_switch],
                CONF_CYCLE_TIME: {"seconds": cycle_time},
            }
        },
    )
    await hass.async_block_till_done()

    # On initialize value is 0, so output should be off
    assert hass.states.get(slow_pwm).state == "0.0"
    assert hass.states.get(output_switch).state == STATE_OFF

    # Now set value to 90%, see if output goes on
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 90, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(slow_pwm).state == "90.0"
    assert hass.states.get(output_switch).state == STATE_ON

    # Decrease value to 1%, see if output goes off
    await asyncio.sleep(cycle_time * 0.02)
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 1, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(slow_pwm).state == "1.0"
    assert hass.states.get(output_switch).state == STATE_OFF

    # Now increase to 80%, see if output goes on again
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 80, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(slow_pwm).state == "80.0"
    assert hass.states.get(output_switch).state == STATE_ON
    # Set value to 0 to stop lingering times before we return
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 0, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )


async def test_minimal_switch_time(hass: HomeAssistant, setup_comp) -> None:
    """Test minimal switching time parameter."""
    output_switch = "input_boolean.test"
    slow_pwm = f"{Platform.NUMBER}.test"
    cycle_time = 10
    minimal_switch_time = 3
    assert await async_setup_component(
        hass, input_boolean.DOMAIN, {"input_boolean": {"test": None}}
    )

    assert await async_setup_component(
        hass,
        Platform.NUMBER,
        {
            Platform.NUMBER: {
                CONF_PLATFORM: DOMAIN,
                CONF_NAME: "test",
                CONF_OUTPUTS: [output_switch],
                CONF_CYCLE_TIME: {"seconds": cycle_time},
                CONF_MIN_SWITCH_TIME: {"seconds": minimal_switch_time},
            }
        },
    )
    await hass.async_block_till_done()

    # On initialize value is 0, so output should be off
    assert hass.states.get(slow_pwm).state == "0.0"
    assert hass.states.get(output_switch).state == STATE_OFF

    # Set value to 5%, output should stay off
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 5, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(slow_pwm).state == "5.0"
    assert hass.states.get(output_switch).state == STATE_OFF

    # Set value to 40%, output should switch on
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 40, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(slow_pwm).state == "40.0"
    assert hass.states.get(output_switch).state == STATE_ON

    # Set value to 90%, output should stay continuously
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 90, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(slow_pwm).state == "90.0"
    await asyncio.sleep(cycle_time * 0.9)
    assert hass.states.get(output_switch).state == STATE_ON

    # Set value to 0 to stop lingering times before we return
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 0, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )


async def test_output_does_not_exist(hass: HomeAssistant, setup_comp, caplog) -> None:
    """Test output does not exist."""
    output_switch = "input_boolean.test"
    slow_pwm = f"{Platform.NUMBER}.test"
    assert await async_setup_component(
        hass,
        Platform.NUMBER,
        {
            Platform.NUMBER: {
                CONF_PLATFORM: DOMAIN,
                CONF_NAME: "test",
                CONF_OUTPUTS: [output_switch],
            }
        },
    )
    await hass.async_block_till_done()

    # On initialize value is 0, so output should be off
    assert hass.states.get(slow_pwm).state == "0.0"

    # clear logging
    caplog.clear()
    # Set value to 100%
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 100, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )
    assert hass.states.get(slow_pwm).state == "100.0"
    # test if a warning was generated
    assert "WARNING" in caplog.text
    assert await hass.services.async_call(
        "homeassistant",
        "stop",
        None,
        blocking=True,
    )
    # Set value to 0 to stop lingering times before we return
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 0, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )


async def test_outside_range(hass: HomeAssistant, setup_comp) -> None:
    """Test what happens if we write a value outside the range."""
    output_switch = "input_boolean.test"
    slow_pwm = f"{Platform.NUMBER}.test"
    minimum = 20
    maximum = 30
    assert await async_setup_component(
        hass, input_boolean.DOMAIN, {"input_boolean": {"test": None}}
    )
    assert await async_setup_component(
        hass,
        Platform.NUMBER,
        {
            Platform.NUMBER: {
                CONF_PLATFORM: DOMAIN,
                CONF_NAME: "test",
                CONF_OUTPUTS: [output_switch],
                CONF_MINIMUM: minimum,
                CONF_MAXIMUM: maximum,
            }
        },
    )
    await hass.async_block_till_done()
    # On initialize value is 20, so output should be off
    assert hass.states.get(slow_pwm).state == "20.0"
    assert hass.states.get(output_switch).state == STATE_OFF

    # Change to 25
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 25, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )
    assert hass.states.get(slow_pwm).state == "25.0"

    # Set value to 0. This should generate a ValueError in the number component
    with pytest.raises(Exception):
        await hass.services.async_call(
            Platform.NUMBER,
            SERVICE_SET_VALUE,
            {ATTR_VALUE: 0, ATTR_ENTITY_ID: slow_pwm},
            blocking=True,
        )
    # Check if value is changed
    assert hass.states.get(slow_pwm).state == "25.0"

    # Set value to 80. This should generate a warning, value should not change
    with pytest.raises(Exception):
        await hass.services.async_call(
            Platform.NUMBER,
            SERVICE_SET_VALUE,
            {ATTR_VALUE: 80, ATTR_ENTITY_ID: slow_pwm},
            blocking=True,
        )
    # test if a warning was generated
    assert hass.states.get(slow_pwm).state == "25.0"
    assert await hass.services.async_call(
        "homeassistant",
        "stop",
        None,
        blocking=True,
    )
    # Set value to 20 to stop lingering times before we return
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: minimum, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )


async def test_bad_value(hass: HomeAssistant, setup_comp, caplog) -> None:
    """Test what happens if we send a bad value."""
    output_switch = "input_boolean.test"
    slow_pwm = f"{Platform.NUMBER}.test"
    assert await async_setup_component(
        hass, input_boolean.DOMAIN, {"input_boolean": {"test": None}}
    )
    assert await async_setup_component(
        hass,
        Platform.NUMBER,
        {
            Platform.NUMBER: {
                CONF_PLATFORM: DOMAIN,
                CONF_NAME: "test",
                CONF_OUTPUTS: [output_switch],
            }
        },
    )
    await hass.async_block_till_done()

    # On initialize value is 0, output should be off
    assert hass.states.get(slow_pwm).state == "0.0"
    assert hass.states.get(output_switch).state == STATE_OFF

    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 42, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )
    assert hass.states.get(slow_pwm).state == "42.0"

    # Set value to "infinity". This should generate an exception, value should remain what it was
    with pytest.raises(Exception):
        await hass.services.async_call(
            Platform.NUMBER,
            SERVICE_SET_VALUE,
            {ATTR_VALUE: "inf", ATTR_ENTITY_ID: slow_pwm},
            blocking=True,
        )
    assert hass.states.get(slow_pwm).state == "42.0"

    # Set value to "nan". This should generate a warning, value should remain what it was
    caplog.clear()
    await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: "nan", ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )
    assert hass.states.get(slow_pwm).state == "42.0"
    # test if a warning was generated
    assert "WARNING" in caplog.text
    assert await hass.services.async_call(
        "homeassistant",
        "stop",
        None,
        blocking=True,
    )
    # Set value to 0 to stop lingering times before we return
    assert await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 0, ATTR_ENTITY_ID: slow_pwm},
        blocking=True,
    )


async def test_reload(hass: HomeAssistant, setup_comp) -> None:
    """Verify we can reload filter sensors."""
    output_switches = ["input_boolean.test1", "input_boolean.test2"]
    slow_pwm = f"{Platform.NUMBER}.test"
    assert await async_setup_component(
        hass, input_boolean.DOMAIN, {"input_boolean": {"test1": None, "test2": None}}
    )

    assert await async_setup_component(
        hass,
        Platform.NUMBER,
        {
            Platform.NUMBER: {
                CONF_PLATFORM: DOMAIN,
                CONF_NAME: "test",
                CONF_OUTPUTS: output_switches,
            }
        },
    )
    await hass.async_block_till_done()

    # On initialize value is 0, so output should be off
    assert hass.states.get(slow_pwm).state == "0.0"
    assert hass.states.get(output_switches[0]).state == STATE_OFF
    assert hass.states.get(output_switches[1]).state == STATE_OFF
    assert len(hass.states.async_all()) == 3

    yaml_path = get_fixture_path("configuration.yaml", "slow_pwm")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 3
    assert hass.states.get("number.test") is None
    assert hass.states.get("number.second_test")
