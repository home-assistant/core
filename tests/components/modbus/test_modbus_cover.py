"""The tests for the Modbus cover component."""
import pytest

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.modbus.const import CALL_TYPE_COIL, CONF_REGISTER
from homeassistant.const import (
    CONF_COVERS,
    CONF_NAME,
    CONF_SLAVE,
    STATE_OPEN,
    STATE_OPENING,
)

from .conftest import base_test


@pytest.mark.parametrize(
    "regs,expected",
    [
        (
            [0x00],
            STATE_OPENING,
        ),
        (
            [0x80],
            STATE_OPENING,
        ),
        (
            [0xFE],
            STATE_OPENING,
        ),
        (
            [0xFF],
            STATE_OPENING,
        ),
        (
            [0x01],
            STATE_OPENING,
        ),
    ],
)
async def test_coil_cover(hass, regs, expected):
    """Run test for given config."""
    cover_name = "modbus_test_cover"
    await base_test(
        cover_name,
        hass,
        {
            CONF_COVERS: [
                {
                    CONF_NAME: cover_name,
                    CALL_TYPE_COIL: 1234,
                    CONF_SLAVE: 1,
                },
            ]
        },
        COVER_DOMAIN,
        5,
        regs,
        expected,
        method_discovery=True,
    )


@pytest.mark.parametrize(
    "regs,expected",
    [
        (
            [0x00],
            STATE_OPEN,
        ),
        (
            [0x80],
            STATE_OPEN,
        ),
        (
            [0xFE],
            STATE_OPEN,
        ),
        (
            [0xFF],
            STATE_OPEN,
        ),
        (
            [0x01],
            STATE_OPEN,
        ),
    ],
)
async def test_register_COVER(hass, regs, expected):
    """Run test for given config."""
    cover_name = "modbus_test_cover"
    await base_test(
        cover_name,
        hass,
        {
            CONF_COVERS: [
                {
                    CONF_NAME: cover_name,
                    CONF_REGISTER: 1234,
                    CONF_SLAVE: 1,
                },
            ]
        },
        COVER_DOMAIN,
        5,
        regs,
        expected,
        method_discovery=True,
    )
