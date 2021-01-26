"""The tests for the Modbus switch component."""
from datetime import timedelta

import pytest

from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_REGISTER_HOLDING,
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

from .conftest import run_base_read_test, setup_base_test


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
async def test_coil_switch(hass, mock_hub, regs, expected):
    """Run test for given config."""
    switch_name = "modbus_test_switch"
    scan_interval = 5
    entity_id, now, device = await setup_base_test(
        switch_name,
        hass,
        mock_hub,
        {
            CONF_COILS: [
                {CONF_NAME: switch_name, CALL_TYPE_COIL: 1234, CONF_SLAVE: 1},
            ]
        },
        SWITCH_DOMAIN,
        scan_interval,
    )

    await run_base_read_test(
        entity_id,
        hass,
        mock_hub,
        CALL_TYPE_COIL,
        regs,
        expected,
        now + timedelta(seconds=scan_interval + 1),
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
async def test_register_switch(hass, mock_hub, regs, expected):
    """Run test for given config."""
    switch_name = "modbus_test_switch"
    scan_interval = 5
    entity_id, now, device = await setup_base_test(
        switch_name,
        hass,
        mock_hub,
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
        scan_interval,
    )

    await run_base_read_test(
        entity_id,
        hass,
        mock_hub,
        CALL_TYPE_REGISTER_HOLDING,
        regs,
        expected,
        now + timedelta(seconds=scan_interval + 1),
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
async def test_register_state_switch(hass, mock_hub, regs, expected):
    """Run test for given config."""
    switch_name = "modbus_test_switch"
    scan_interval = 5
    entity_id, now, device = await setup_base_test(
        switch_name,
        hass,
        mock_hub,
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
        scan_interval,
    )

    await run_base_read_test(
        entity_id,
        hass,
        mock_hub,
        CALL_TYPE_REGISTER_HOLDING,
        regs,
        expected,
        now + timedelta(seconds=scan_interval + 1),
    )
