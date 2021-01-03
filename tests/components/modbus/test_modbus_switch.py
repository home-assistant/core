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

from .conftest import base_test


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
async def test_coil_switch(hass, ModbusHubMock, regs, expected):
    """Run test for given config."""
    switch_name = "modbus_test_switch"
    await base_test(
        switch_name,
        hass,
        {
            CONF_COILS: [
                {CONF_NAME: switch_name, CALL_TYPE_COIL: 1234, CONF_SLAVE: 1},
            ]
        },
        SWITCH_DOMAIN,
        5,
        regs,
        expected,
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
            STATE_OFF,
        ),
        (
            [0x01],
            STATE_ON,
        ),
    ],
)
async def test_register_switch(hass, ModbusHubMock, regs, expected):
    """Run test for given config."""
    switch_name = "modbus_test_switch"
    await base_test(
        switch_name,
        hass,
        {
            CONF_REGISTERS: [
                {
                    CONF_NAME: switch_name,
                    CONF_REGISTER: 1234,
                    CONF_SLAVE: 1,
                    CONF_COMMAND_OFF: 0x00,
                    CONF_COMMAND_ON: 0x01,
                },
            ]
        },
        SWITCH_DOMAIN,
        5,
        regs,
        expected,
    )


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
async def test_register_state_switch(hass, ModbusHubMock, regs, expected):
    """Run test for given config."""
    switch_name = "modbus_test_switch"
    await base_test(
        switch_name,
        hass,
        {
            CONF_REGISTERS: [
                {
                    CONF_NAME: switch_name,
                    CONF_REGISTER: 1234,
                    CONF_SLAVE: 1,
                    CONF_COMMAND_OFF: 0x04,
                    CONF_COMMAND_ON: 0x40,
                },
            ]
        },
        SWITCH_DOMAIN,
        5,
        regs,
        expected,
    )
