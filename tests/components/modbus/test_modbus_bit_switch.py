"""The tests for the Modbus switch component."""
import pytest

from homeassistant.components.modbus.const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_BIT_SWITCHES,
    CONF_COMMAND_BIT_NUMBER,
    CONF_INPUT_TYPE,
    CONF_REGISTERS,
    CONF_STATUS_BIT_NUMBER,
    CONF_VERIFY_REGISTER,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SLAVE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)

from .conftest import base_config_test, base_test


@pytest.mark.parametrize("do_options", [False, True])
@pytest.mark.parametrize(
    "read_type", [CALL_TYPE_REGISTER_HOLDING, CALL_TYPE_REGISTER_INPUT]
)
async def test_config_switch(hass, do_options, read_type):
    """Run test for switch."""
    device_name = "test_switch"

    device_config = {
        CONF_NAME: device_name,
        CONF_INPUT_TYPE: read_type,
        CONF_COMMAND_BIT_NUMBER: 5,
    }
    array_type = None
    device_config[CONF_ADDRESS] = 1234

    if do_options:
        device_config[CONF_SLAVE] = 1
        device_config.update({CONF_STATUS_BIT_NUMBER: 6, CONF_VERIFY_REGISTER: 1235})
        device_config.update(
            {
                CONF_DEVICE_CLASS: "switch",
                CONF_INPUT_TYPE: read_type,
            }
        )

    await base_config_test(
        hass,
        device_config,
        device_name,
        SWITCH_DOMAIN,
        CONF_BIT_SWITCHES,
        array_type,
        method_discovery=True,
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
            STATE_ON,
        ),
        (
            [0xFF],
            STATE_ON,
        ),
        (
            [0x01],
            STATE_OFF,
        ),
        (
            [0x20],
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
            CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
            CONF_ADDRESS: 1234,
            CONF_SLAVE: 1,
            CONF_COMMAND_BIT_NUMBER: 5,
        },
        switch_name,
        SWITCH_DOMAIN,
        CONF_BIT_SWITCHES,
        CONF_REGISTERS,
        regs,
        expected,
        method_discovery=True,
        scan_interval=5,
    )
    assert state == expected


@pytest.mark.parametrize(
    "regs,expected,service,write_register",
    [
        ([0x00], STATE_OFF, SERVICE_TURN_ON, ([1234, 0x40], {"unit": 1})),
        (
            [0x41],
            STATE_OFF,
            SERVICE_TURN_ON,
            # 0x40 yields OFF state due to the status bit 5
            # however, SERVICE_TURN_ON enables bit 6 which make bit untouched
            ([1234, 0x41], {"unit": 1}),
        ),
        ([0x60], STATE_ON, SERVICE_TURN_OFF, ([1234, 0x20], {"unit": 1})),
    ],
)
async def test_register_switch_service(hass, regs, expected, service, write_register):
    """Run test for given config."""
    switch_name = "modbus_test_switch"
    call_service = {"domain": SWITCH_DOMAIN, "service": service}
    state = await base_test(
        hass,
        {
            CONF_NAME: switch_name,
            CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
            CONF_ADDRESS: 1234,
            CONF_SLAVE: 1,
            CONF_COMMAND_BIT_NUMBER: 6,
            CONF_STATUS_BIT_NUMBER: 5,
        },
        switch_name,
        SWITCH_DOMAIN,
        CONF_BIT_SWITCHES,
        CONF_REGISTERS,
        regs,
        expected,
        method_discovery=True,
        scan_interval=5,
        call_service=call_service,
        write_register=write_register,
    )
    assert state == expected
