"""The tests for the Modbus sensor component."""
import pytest

from homeassistant.components.binary_sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CONF_INPUT_TYPE,
    CONF_INPUTS,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_SLAVE, STATE_OFF, STATE_ON

from .conftest import base_config_test, base_test


@pytest.mark.parametrize("do_options", [False, True])
async def test_config_binary_sensor(hass, do_options):
    """Run test for binary sensor."""
    sensor_name = "test_sensor"
    config_sensor = {
        CONF_NAME: sensor_name,
        CONF_ADDRESS: 51,
    }
    if do_options:
        config_sensor.update(
            {
                CONF_SLAVE: 10,
                CONF_INPUT_TYPE: CALL_TYPE_DISCRETE,
            }
        )
    await base_config_test(
        hass,
        config_sensor,
        sensor_name,
        SENSOR_DOMAIN,
        None,
        CONF_INPUTS,
        method_discovery=False,
    )


@pytest.mark.parametrize("do_type", [CALL_TYPE_COIL, CALL_TYPE_DISCRETE])
@pytest.mark.parametrize(
    "regs,expected",
    [
        (
            [0xFF],
            STATE_ON,
        ),
        (
            [0x01],
            STATE_ON,
        ),
        (
            [0x00],
            STATE_OFF,
        ),
        (
            [0x80],
            STATE_OFF,
        ),
        (
            [0xFE],
            STATE_OFF,
        ),
    ],
)
async def test_all_binary_sensor(hass, do_type, regs, expected):
    """Run test for given config."""
    sensor_name = "modbus_test_binary_sensor"
    state = await base_test(
        hass,
        {CONF_NAME: sensor_name, CONF_ADDRESS: 1234, CONF_INPUT_TYPE: do_type},
        sensor_name,
        SENSOR_DOMAIN,
        None,
        CONF_INPUTS,
        regs,
        expected,
        method_discovery=False,
        scan_interval=5,
    )
    assert state == expected
