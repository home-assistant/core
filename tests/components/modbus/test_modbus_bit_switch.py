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
    CONF_VERIFY_STATE,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ADDRESS,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SLAVE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
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
        (None, STATE_UNAVAILABLE),
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
    "regs,service,write_register_call_args,verify_state,expected",
    [
        ([0x00], SERVICE_TURN_ON, ([1234, 0x40], {"unit": 1}), True, STATE_OFF),
        # CONF_VERIFY_STATE False immediately update the state
        ([0x00], SERVICE_TURN_ON, ([1234, 0x40], {"unit": 1}), False, STATE_ON),
        (
            [0x41],
            SERVICE_TURN_ON,
            # 0x41 yields OFF state since CONF_STATUS_BIT_NUMBER is 5
            # however, SERVICE_TURN_ON set bit 6 which is ON already
            ([1234, 0x41], {"unit": 1}),
            True,
            STATE_OFF,
        ),
        ([0x60], SERVICE_TURN_OFF, ([1234, 0x20], {"unit": 1}), True, STATE_ON),
        ([0x60], SERVICE_TURN_OFF, ([1234, 0x20], {"unit": 1}), False, STATE_OFF),
    ],
)
async def test_register_switch_service(
    hass, regs, service, write_register_call_args, verify_state, expected
):
    """Run test for given config."""
    switch_name = "modbus_test_switch"

    async def _mock_hook(mock):
        # Call an arbitrary service
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: f"{SWITCH_DOMAIN}.{switch_name}"},
            blocking=True,
        )
        await hass.async_block_till_done()

        # check the register write has been called
        args, kvargs = write_register_call_args
        mock.write_register.assert_called_once_with(*args, **kvargs)

    state = await base_test(
        hass,
        {
            CONF_NAME: switch_name,
            CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
            CONF_ADDRESS: 1234,
            CONF_SLAVE: 1,
            CONF_COMMAND_BIT_NUMBER: 6,
            CONF_STATUS_BIT_NUMBER: 5,
            CONF_VERIFY_STATE: verify_state,
        },
        switch_name,
        SWITCH_DOMAIN,
        CONF_BIT_SWITCHES,
        CONF_REGISTERS,
        regs,
        expected,
        method_discovery=True,
        scan_interval=5,
        mock_hook=_mock_hook,
    )
    assert state == expected
