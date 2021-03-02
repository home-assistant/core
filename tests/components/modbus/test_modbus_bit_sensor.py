"""The tests for the Modbus sensor component."""
import pytest

from homeassistant.components.modbus.const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_BIT_NUMBER,
    CONF_BIT_SENSORS,
    CONF_COUNT,
    CONF_INPUT_TYPE,
    CONF_REGISTERS,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SLAVE,
    STATE_UNAVAILABLE,
)

from .conftest import base_config_test, base_test


@pytest.mark.parametrize("do_options", [False, True])
@pytest.mark.parametrize(
    "do_type", [CALL_TYPE_REGISTER_HOLDING, CALL_TYPE_REGISTER_INPUT]
)
async def test_config_sensor(hass, do_options, do_type):
    """Run test for sensor."""
    sensor_name = "test_sensor"
    config_sensor = {CONF_NAME: sensor_name, CONF_ADDRESS: 51, CONF_BIT_NUMBER: 5}
    if do_options:
        config_sensor.update(
            {
                CONF_SLAVE: 10,
                CONF_INPUT_TYPE: do_type,
                CONF_DEVICE_CLASS: "battery",
            }
        )
    await base_config_test(
        hass,
        config_sensor,
        sensor_name,
        SENSOR_DOMAIN,
        CONF_BIT_SENSORS,
        CONF_REGISTERS,
        method_discovery=True,
    )


@pytest.mark.parametrize(
    "cfg,regs,expected",
    [
        (
            {},
            [0],
            "False",
        ),
        (
            {},
            None,
            STATE_UNAVAILABLE,
        ),
        (
            {},
            [0x20],
            "True",
        ),
        (
            {},
            [0xFF],
            "True",
        ),
        (
            {},
            [0xDF],
            "False",
        ),
        (
            {CONF_BIT_NUMBER: 15},
            [0x8000],
            "True",
        ),
        (
            {CONF_BIT_NUMBER: 15},
            [0x7FFF],
            "False",
        ),
        (
            {CONF_BIT_NUMBER: 31, CONF_COUNT: 2},
            [0x0000, 0x8000],
            "True",
        ),
        (
            {CONF_BIT_NUMBER: 63, CONF_COUNT: 4},
            [0x0000, 0x0000, 0x0000, 0x8000],
            "True",
        ),
        (
            {CONF_BIT_NUMBER: 28, CONF_COUNT: 4},
            [0x0000, 0x1000, 0x0000, 0x0000],
            "True",
        ),
    ],
)
async def test_all_bit_sensor(hass, cfg, regs, expected):
    """Run test for sensor."""
    sensor_name = "modbus_test_sensor"
    state = await base_test(
        hass,
        {
            CONF_NAME: sensor_name,
            CONF_ADDRESS: 1234,
            CONF_BIT_NUMBER: 5,
            **cfg,
        },
        sensor_name,
        SENSOR_DOMAIN,
        CONF_BIT_SENSORS,
        CONF_REGISTERS,
        regs,
        expected,
        method_discovery=True,
        scan_interval=5,
    )
    assert state == expected
