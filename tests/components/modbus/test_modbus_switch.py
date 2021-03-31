"""The tests for the Modbus switch component."""
import pytest

from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CONF_COILS,
    CONF_REGISTER,
    CONF_REGISTERS,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_NAME,
    CONF_SLAVE,
    STATE_OFF,
    STATE_ON,
)

from .conftest import base_config_test, base_test


@pytest.mark.parametrize("do_options", [False, True])
@pytest.mark.parametrize("read_type", [CALL_TYPE_COIL, CONF_REGISTER])
async def test_config_switch(hass, do_options, read_type):
    """Run test for switch."""
    device_name = "test_switch"

    if read_type == CONF_REGISTER:
        device_config = {
            CONF_NAME: device_name,
            CONF_REGISTER: 1234,
            CONF_SLAVE: 1,
            CONF_COMMAND_OFF: 0x00,
            CONF_COMMAND_ON: 0x01,
        }
        array_type = CONF_REGISTERS
    else:
        device_config = {
            CONF_NAME: device_name,
            read_type: 1234,
            CONF_SLAVE: 10,
        }
        array_type = CONF_COILS
    if do_options:
        device_config.update({})

    await base_config_test(
        hass,
        device_config,
        device_name,
        SWITCH_DOMAIN,
        None,
        array_type,
        method_discovery=False,
    )


@pytest.mark.parametrize(
    "regs,expected",
    [
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
        (
            [0xFF],
            STATE_ON,
        ),
        (
            [0x01],
            STATE_ON,
        ),
    ],
)
async def test_coil_switch(hass, regs, expected):
    """Run test for given config."""
    switch_name = "modbus_test_switch"
    state = await base_test(
        hass,
        {
            CONF_NAME: switch_name,
            CALL_TYPE_COIL: 1234,
            CONF_SLAVE: 1,
        },
        switch_name,
        SWITCH_DOMAIN,
        None,
        CONF_COILS,
        regs,
        expected,
        method_discovery=False,
        scan_interval=5,
    )
    assert state == expected


@pytest.mark.parametrize(
    "regs,expected",
    [
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
        (
            [0xFF],
            STATE_OFF,
        ),
        (
            [0x01],
            STATE_ON,
        ),
    ],
)
async def test_register_switch(hass, regs, expected):
    """Run test for given config."""
    switch_name = "modbus_test_switch"
    state = await base_test(
        hass,
        {
            CONF_NAME: switch_name,
            CONF_REGISTER: 1234,
            CONF_SLAVE: 1,
            CONF_COMMAND_OFF: 0x00,
            CONF_COMMAND_ON: 0x01,
        },
        switch_name,
        SWITCH_DOMAIN,
        None,
        CONF_REGISTERS,
        regs,
        expected,
        method_discovery=False,
        scan_interval=5,
    )
    assert state == expected


@pytest.mark.parametrize(
    "regs,expected",
    [
        (
            [0x40],
            STATE_ON,
        ),
        (
            [0x04],
            STATE_OFF,
        ),
        (
            [0xFF],
            STATE_OFF,
        ),
    ],
)
async def test_register_state_switch(hass, regs, expected):
    """Run test for given config."""
    switch_name = "modbus_test_switch"
    state = await base_test(
        hass,
        {
            CONF_NAME: switch_name,
            CONF_REGISTER: 1234,
            CONF_SLAVE: 1,
            CONF_COMMAND_OFF: 0x04,
            CONF_COMMAND_ON: 0x40,
        },
        switch_name,
        SWITCH_DOMAIN,
        None,
        CONF_REGISTERS,
        regs,
        expected,
        method_discovery=False,
        scan_interval=5,
    )
    assert state == expected
