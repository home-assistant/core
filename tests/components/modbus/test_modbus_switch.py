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
    CONF_SWITCHES,
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
    STATE_OFF,
    STATE_ON,
)

from .conftest import base_config_test, base_test


@pytest.mark.parametrize("do_discovery", [False, True])
@pytest.mark.parametrize("do_options", [False, True])
@pytest.mark.parametrize(
    "read_type", [CALL_TYPE_REGISTER_HOLDING, CALL_TYPE_REGISTER_INPUT, CALL_TYPE_COIL]
)
async def test_config_switch(hass, do_discovery, do_options, read_type):
    """Run test for switch."""
    device_name = "test_switch"

    device_config = {
        CONF_NAME: device_name,
    }
    if not do_discovery:
        if read_type == CALL_TYPE_COIL:
            array_type = CONF_COILS
            device_config[CALL_TYPE_COIL] = 1234
            device_config[CONF_SLAVE] = 1
        else:
            array_type = CONF_REGISTERS
            device_config[CONF_REGISTER] = 1234
            device_config[CONF_COMMAND_OFF] = 0x00
            device_config[CONF_COMMAND_ON] = 0x01
    else:
        array_type = None
        device_config[CONF_ADDRESS] = 1234
        if read_type == CALL_TYPE_COIL:
            device_config[CONF_INPUT_TYPE] = CALL_TYPE_COIL

    if do_options:
        device_config[CONF_SLAVE] = 1
        if read_type != CALL_TYPE_COIL:
            device_config.update(
                {
                    CONF_STATE_OFF: 0,
                    CONF_STATE_ON: 1,
                    CONF_VERIFY_REGISTER: 1235,
                    CONF_COMMAND_OFF: 0x00,
                    CONF_COMMAND_ON: 0x01,
                }
            )
        if do_discovery:
            device_config.update(
                {
                    CONF_DEVICE_CLASS: "switch",
                    CONF_INPUT_TYPE: read_type,
                }
            )
        else:
            if read_type != CALL_TYPE_COIL:
                device_config[CONF_VERIFY_STATE] = True
                device_config[CONF_REGISTER_TYPE] = read_type

    await base_config_test(
        hass,
        device_config,
        device_name,
        SWITCH_DOMAIN,
        CONF_SWITCHES,
        array_type,
        method_discovery=do_discovery,
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
