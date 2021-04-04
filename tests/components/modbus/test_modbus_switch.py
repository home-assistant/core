"""The tests for the Modbus switch component."""
import pytest

from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_COILS,
    CONF_INPUT_TYPE,
    CONF_REGISTER,
    CONF_REGISTER_TYPE,
    CONF_REGISTERS,
    CONF_STATE_OFF,
    CONF_STATE_ON,
    CONF_VERIFY_REGISTER,
    CONF_VERIFY_STATE,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SLAVE,
    CONF_SWITCHES,
    STATE_OFF,
    STATE_ON,
)

from .conftest import base_config_test, base_test


@pytest.mark.parametrize(
    "array_type, do_config",
    [
        (
            None,
            {
                CONF_ADDRESS: 1234,
            },
        ),
        (
            None,
            {
                CONF_ADDRESS: 1234,
                CONF_INPUT_TYPE: CALL_TYPE_COIL,
            },
        ),
        (
            None,
            {
                CONF_ADDRESS: 1234,
                CONF_SLAVE: 1,
                CONF_STATE_OFF: 0,
                CONF_STATE_ON: 1,
                CONF_VERIFY_REGISTER: 1235,
                CONF_VERIFY_STATE: False,
                CONF_COMMAND_OFF: 0x00,
                CONF_COMMAND_ON: 0x01,
                CONF_DEVICE_CLASS: "switch",
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
            },
        ),
        (
            None,
            {
                CONF_ADDRESS: 1234,
                CONF_SLAVE: 1,
                CONF_STATE_OFF: 0,
                CONF_STATE_ON: 1,
                CONF_VERIFY_REGISTER: 1235,
                CONF_VERIFY_STATE: True,
                CONF_COMMAND_OFF: 0x00,
                CONF_COMMAND_ON: 0x01,
                CONF_DEVICE_CLASS: "switch",
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
            },
        ),
        (
            None,
            {
                CONF_ADDRESS: 1234,
                CONF_INPUT_TYPE: CALL_TYPE_COIL,
                CONF_SLAVE: 1,
                CONF_DEVICE_CLASS: "switch",
                CONF_INPUT_TYPE: CALL_TYPE_COIL,
            },
        ),
        (
            CONF_REGISTERS,
            {
                CONF_REGISTER: 1234,
                CONF_COMMAND_OFF: 0x00,
                CONF_COMMAND_ON: 0x01,
            },
        ),
        (
            CONF_REGISTERS,
            {
                CONF_REGISTER: 1234,
                CONF_COMMAND_OFF: 0x00,
                CONF_COMMAND_ON: 0x01,
            },
        ),
        (
            CONF_COILS,
            {
                CALL_TYPE_COIL: 1234,
                CONF_SLAVE: 1,
            },
        ),
        (
            CONF_REGISTERS,
            {
                CONF_REGISTER: 1234,
                CONF_COMMAND_OFF: 0x00,
                CONF_COMMAND_ON: 0x01,
                CONF_SLAVE: 1,
                CONF_STATE_OFF: 0,
                CONF_STATE_ON: 1,
                CONF_VERIFY_REGISTER: 1235,
                CONF_COMMAND_OFF: 0x00,
                CONF_COMMAND_ON: 0x01,
                CONF_VERIFY_STATE: True,
                CONF_REGISTER_TYPE: CALL_TYPE_REGISTER_INPUT,
            },
        ),
        (
            CONF_REGISTERS,
            {
                CONF_REGISTER: 1234,
                CONF_COMMAND_OFF: 0x00,
                CONF_COMMAND_ON: 0x01,
                CONF_SLAVE: 1,
                CONF_STATE_OFF: 0,
                CONF_STATE_ON: 1,
                CONF_VERIFY_REGISTER: 1235,
                CONF_COMMAND_OFF: 0x00,
                CONF_COMMAND_ON: 0x01,
                CONF_VERIFY_STATE: True,
                CONF_REGISTER_TYPE: CALL_TYPE_REGISTER_HOLDING,
            },
        ),
        (
            CONF_COILS,
            {
                CALL_TYPE_COIL: 1234,
                CONF_SLAVE: 1,
            },
        ),
    ],
)
async def test_config_switch(hass, array_type, do_config):
    """Run test for switch."""
    device_name = "test_switch"

    device_config = {
        CONF_NAME: device_name,
        **do_config,
    }

    await base_config_test(
        hass,
        device_config,
        device_name,
        SWITCH_DOMAIN,
        CONF_SWITCHES,
        array_type,
        method_discovery=(array_type is None),
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
            CONF_ADDRESS: 1234,
            CONF_INPUT_TYPE: CALL_TYPE_COIL,
        },
        switch_name,
        SWITCH_DOMAIN,
        CONF_SWITCHES,
        CONF_COILS,
        regs,
        expected,
        method_discovery=True,
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
        CONF_SWITCHES,
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
        CONF_SWITCHES,
        CONF_REGISTERS,
        regs,
        expected,
        method_discovery=False,
        scan_interval=5,
    )
    assert state == expected
