"""The tests for the Modbus switch component."""
from unittest import mock

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
    MODBUS_DOMAIN,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ADDRESS,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SLAVE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)

from .conftest import base_config_test, base_test, server_test


@pytest.mark.parametrize("do_options", [False, True])
@pytest.mark.parametrize(
    "read_type", [CALL_TYPE_REGISTER_HOLDING, CALL_TYPE_REGISTER_INPUT]
)
@pytest.mark.parametrize("do_server", [False, True])
@mock.patch("homeassistant.components.modbus.modbus.StartTcpServer")
async def test_config_switch(
    mock_server, hass, do_options, read_type, do_server, config_modbus_server
):
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
        config_modbus=config_modbus_server if do_server else None,
    )
    if do_server:
        mock_server.assert_called_once_with(
            mock.ANY,
            address=(
                config_modbus_server[MODBUS_DOMAIN][CONF_HOST],
                config_modbus_server[MODBUS_DOMAIN][CONF_PORT],
            ),
            allow_reuse_address=True,
            defer_start=True,
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
@pytest.mark.parametrize("do_server", [True, False])
async def test_register_switch(do_server, config_modbus_server, hass, regs, expected):
    """Run test for given config."""
    switch_name = "modbus_test_switch"
    if do_server:
        state, _ = await server_test(
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
            config_modbus=config_modbus_server,
        )

    else:
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
    "regs,service,call_args,verify_state,expected",
    [
        ([0x00], SERVICE_TURN_ON, [1234, 0x40], True, STATE_OFF),
        # CONF_VERIFY_STATE False immediately update the state
        ([0x00], SERVICE_TURN_ON, [1234, 0x40], False, STATE_ON),
        (
            [0x41],
            SERVICE_TURN_ON,
            # 0x41 yields OFF state since CONF_STATUS_BIT_NUMBER is 5
            # however, SERVICE_TURN_ON set bit 6 which is ON already
            [1234, 0x41],
            True,
            STATE_OFF,
        ),
        ([0x60], SERVICE_TURN_OFF, [1234, 0x20], True, STATE_ON),
        ([0x60], SERVICE_TURN_OFF, [1234, 0x20], False, STATE_OFF),
    ],
)
@pytest.mark.parametrize("do_server", [True])
async def test_register_switch_service(
    do_server,
    config_modbus_server,
    hass,
    regs,
    service,
    call_args,
    verify_state,
    expected,
):
    """Run test for given config."""
    switch_name = "modbus_test_switch"

    if do_server:

        async def _mock_server_hook(mock):
            # Call an arbitrary service
            await hass.services.async_call(
                SWITCH_DOMAIN,
                service,
                {ATTR_ENTITY_ID: f"{SWITCH_DOMAIN}.{switch_name}"},
                blocking=True,
            )

        state, data_block = await server_test(
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
            config_modbus=config_modbus_server,
            mock_hook=_mock_server_hook,
        )
        # check the register write has been called
        unit, register = call_args
        data_block.setValues.assert_called_once_with(unit, [register])

    else:

        async def _mock_client_hook(mock):
            # Call an arbitrary service
            await hass.services.async_call(
                SWITCH_DOMAIN,
                service,
                {ATTR_ENTITY_ID: f"{SWITCH_DOMAIN}.{switch_name}"},
                blocking=True,
            )
            await hass.async_block_till_done()

            # check the register write has been called
            mock.write_register.assert_called_once_with(*call_args, unit=1)

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
            mock_hook=_mock_client_hook,
        )
    assert state == expected
