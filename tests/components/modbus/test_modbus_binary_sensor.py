"""The tests for the Modbus sensor component."""
import pytest

from homeassistant.components.binary_sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CONF_INPUT_TYPE,
    CONF_INPUTS,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME, STATE_OFF, STATE_ON

from .conftest import base_test


@pytest.mark.parametrize(
    "cfg,regs,expected",
    [
        (
            {
                CONF_INPUT_TYPE: CALL_TYPE_COIL,
            },
            [0xFF],
            STATE_ON,
        ),
        (
            {
                CONF_INPUT_TYPE: CALL_TYPE_COIL,
            },
            [0x01],
            STATE_ON,
        ),
        (
            {
                CONF_INPUT_TYPE: CALL_TYPE_COIL,
            },
            [0x00],
            STATE_OFF,
        ),
        (
            {
                CONF_INPUT_TYPE: CALL_TYPE_COIL,
            },
            [0x80],
            STATE_OFF,
        ),
        (
            {
                CONF_INPUT_TYPE: CALL_TYPE_COIL,
            },
            [0xFE],
            STATE_OFF,
        ),
        (
            {
                CONF_INPUT_TYPE: CALL_TYPE_DISCRETE,
            },
            [0xFF],
            STATE_ON,
        ),
        (
            {
                CONF_INPUT_TYPE: CALL_TYPE_DISCRETE,
            },
            [0x00],
            STATE_OFF,
        ),
    ],
)
async def test_all_binary_sensor(hass, cfg, regs, expected):
    """Run test for given config."""
    sensor_name = "modbus_test_binary_sensor"
    await base_test(
        sensor_name,
        hass,
        {CONF_INPUTS: [dict(**{CONF_NAME: sensor_name, CONF_ADDRESS: 1234}, **cfg)]},
        SENSOR_DOMAIN,
        5,
        regs,
        expected,
    )
