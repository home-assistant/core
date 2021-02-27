"""The tests for the Modbus switch component."""
from collections import namedtuple
from datetime import timedelta
from unittest import mock

from pymodbus.exceptions import ConnectionException, ModbusException
import pytest

from homeassistant.components.modbus.bit_switch import setup_bit_swithes
from homeassistant.components.modbus.const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_BIT_SWITCHES,
    CONF_COMMAND_BIT_NUMBER,
    CONF_INPUT_TYPE,
    CONF_REGISTER,
    CONF_REGISTER_TYPE,
    CONF_REGISTERS,
    CONF_STATUS_BIT_NUMBER,
    CONF_VERIFY_REGISTER,
    CONF_VERIFY_STATE,
)
from homeassistant.components.modbus.modbus import ModbusHub
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ADDRESS,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SLAVE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.util.dt as dt_util

from .conftest import base_config_test, base_test

from tests.common import async_fire_time_changed


@pytest.mark.parametrize(
    "discovery_info,call_count",
    [(None, 0)],
)
@mock.patch("homeassistant.components.modbus.bit_switch._LOGGER")
def test_setup_bit_swithes(mock_logger, discovery_info, call_count):
    """Test setup bit switch."""
    setup_bit_swithes(mock.MagicMock(), discovery_info)
    assert mock_logger.error.call_count == call_count


@pytest.mark.parametrize(
    "array_type,do_config",
    [
        (
            None,
            {
                CONF_ADDRESS: 1234,
                CONF_COMMAND_BIT_NUMBER: 5,
            },
        ),
        (
            None,
            {
                CONF_ADDRESS: 1234,
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                CONF_COMMAND_BIT_NUMBER: 5,
            },
        ),
        (
            None,
            {
                CONF_ADDRESS: 1234,
                CONF_SLAVE: 1,
                CONF_VERIFY_REGISTER: 1235,
                CONF_VERIFY_STATE: False,
                CONF_COMMAND_BIT_NUMBER: 5,
                CONF_DEVICE_CLASS: "switch",
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
            },
        ),
        (
            None,
            {
                CONF_ADDRESS: 1234,
                CONF_SLAVE: 1,
                CONF_COMMAND_BIT_NUMBER: 5,
                CONF_VERIFY_REGISTER: 1235,
                CONF_VERIFY_STATE: True,
                CONF_STATUS_BIT_NUMBER: 6,
                CONF_DEVICE_CLASS: "switch",
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
            },
        ),
        (
            None,
            {
                CONF_ADDRESS: 1234,
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
                CONF_COMMAND_BIT_NUMBER: 5,
                CONF_SLAVE: 1,
                CONF_DEVICE_CLASS: "switch",
            },
        ),
        (
            CONF_REGISTERS,
            {
                CONF_REGISTER: 1234,
                CONF_REGISTER_TYPE: CALL_TYPE_REGISTER_INPUT,
                CONF_SLAVE: 1,
                CONF_COMMAND_OFF: 0x00,
                CONF_COMMAND_ON: 0x01,
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
        CONF_BIT_SWITCHES,
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
        (ModbusException("Modbus Exception"), STATE_UNAVAILABLE),
        (ConnectionException("Modbus Exception"), STATE_UNAVAILABLE),
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


WriteRegisterSuccess = lambda *_: True  # noqa: E731
WriteRegisterFailure = ConnectionException("write_register failed")


@pytest.mark.parametrize(
    "input_type,regs,service,verify_state,write_side_effect,expected",
    [
        # Write register succeeded, optimistically set state to ON and schedule update
        (
            CALL_TYPE_REGISTER_HOLDING,
            [0x00],
            SERVICE_TURN_ON,
            True,
            WriteRegisterSuccess,
            STATE_ON,
        ),
        # Write register failed, schedule state update and return unavailable state
        (
            CALL_TYPE_REGISTER_HOLDING,
            [0x00],
            SERVICE_TURN_ON,
            True,
            WriteRegisterFailure,
            STATE_UNAVAILABLE,
        ),
        # CONF_VERIFY_STATE False immediately update the state
        (
            CALL_TYPE_REGISTER_HOLDING,
            [0x00],
            SERVICE_TURN_ON,
            False,
            WriteRegisterSuccess,
            STATE_ON,
        ),
        (
            CALL_TYPE_REGISTER_HOLDING,
            [0x41],
            SERVICE_TURN_ON,
            # 0x41 yields OFF state since CONF_STATUS_BIT_NUMBER is 5
            # however, SERVICE_TURN_ON set bit 6 which is ON already
            True,
            WriteRegisterSuccess,
            STATE_ON,
        ),
        (
            CALL_TYPE_REGISTER_HOLDING,
            [0x60],
            SERVICE_TURN_OFF,
            True,
            WriteRegisterSuccess,
            STATE_OFF,
        ),
        (
            CALL_TYPE_REGISTER_HOLDING,
            [0x60],
            SERVICE_TURN_OFF,
            False,
            WriteRegisterSuccess,
            STATE_OFF,
        ),
        # Verify state is off, can turn state off for the CALL_TYPE_REGISTER_INPUT
        # Since CALL_TYPE_REGISTER_INPUT does not call write_register, WriteRegisterFailure should
        # not affect the state
        (
            CALL_TYPE_REGISTER_INPUT,
            [0xFF],
            SERVICE_TURN_OFF,
            False,
            WriteRegisterFailure,
            STATE_OFF,
        ),
        # Verify state is on, can not turn the state off
        (
            CALL_TYPE_REGISTER_INPUT,
            [0xFF],
            SERVICE_TURN_OFF,
            True,
            WriteRegisterFailure,
            STATE_ON,
        ),
        (
            CALL_TYPE_REGISTER_INPUT,
            [0x00],
            SERVICE_TURN_ON,
            False,
            WriteRegisterFailure,
            STATE_OFF,
        ),
        (
            CALL_TYPE_REGISTER_INPUT,
            [0x00],
            SERVICE_TURN_ON,
            True,
            WriteRegisterFailure,
            STATE_OFF,
        ),
        (
            CALL_TYPE_REGISTER_HOLDING,
            ModbusException("Modbus Exception"),
            SERVICE_TURN_OFF,
            True,
            WriteRegisterSuccess,
            STATE_UNAVAILABLE,
        ),
    ],
)
async def test_register_switch_service(
    hass, input_type, regs, service, verify_state, write_side_effect, expected
):
    """Run test for given config."""
    switch_name = "modbus_test_switch"
    with mock.patch.object(ModbusHub, "write_register") as mock_write:
        mock_write.side_effect = write_side_effect
        await base_test(
            hass,
            {
                CONF_NAME: switch_name,
                CONF_INPUT_TYPE: input_type,
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
        )

        entity_id = f"{SWITCH_DOMAIN}.{switch_name}"
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        assert hass.states.get(entity_id).state == expected


Registers = namedtuple("Registers", ["registers"])


@pytest.mark.parametrize(
    "read_data,last_state,init_expected,expected",
    [
        (
            [
                ConnectionException("Modbus Exception"),
                ConnectionException("Modbus Exception"),
            ],
            STATE_ON,
            STATE_UNAVAILABLE,
            STATE_UNAVAILABLE,
        ),
        (
            [
                lambda _1, _2, _3: Registers([0x00]),
                lambda _1, _2, _3: Registers([0x00]),
            ],
            STATE_ON,
            STATE_OFF,
            STATE_OFF,
        ),
        (
            [
                lambda _1, _2, _3: Registers([0xFF]),
                lambda _1, _2, _3: Registers([0x00]),
            ],
            STATE_ON,
            STATE_ON,
            STATE_OFF,
        ),
        (
            [
                lambda _1, _2, _3: Registers([0x00]),
                lambda _1, _2, _3: Registers([0x00]),
            ],
            STATE_OFF,
            STATE_OFF,
            STATE_OFF,
        ),
    ],
)
@mock.patch.object(ModbusHub, "read_holding_registers")
async def test_register_switch_last_state(
    mock_read, hass, read_data, last_state, init_expected, expected
):
    """Run test for given config."""
    mock_read.side_effect = read_data[0]
    switch_name = "modbus_test_switch"
    scan_interval = 1
    with mock.patch.object(RestoreEntity, "async_get_last_state") as last_state_mock:
        last_state_mock.return_value = mock.MagicMock()
        last_state_mock.return_value.state = last_state

        state = await base_test(
            hass,
            {
                CONF_NAME: switch_name,
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                CONF_ADDRESS: 1234,
                CONF_SLAVE: 1,
                CONF_COMMAND_BIT_NUMBER: 6,
                CONF_STATUS_BIT_NUMBER: 5,
                CONF_VERIFY_STATE: True,
            },
            switch_name,
            SWITCH_DOMAIN,
            CONF_BIT_SWITCHES,
            CONF_REGISTERS,
            [0x00],
            STATE_UNAVAILABLE,
            method_discovery=True,
            scan_interval=scan_interval,
        )
        assert state == init_expected, "Init state mismatch"

        mock_read.side_effect = read_data[1]

        entity_id = f"{SWITCH_DOMAIN}.{switch_name}"
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        now = dt_util.utcnow()
        now = now + timedelta(seconds=scan_interval + 120)
        with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
            async_fire_time_changed(hass, now)
            await hass.async_block_till_done()

        assert hass.states.get(entity_id).state == expected
