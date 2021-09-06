"""The tests for the Modbus cover component."""

from pymodbus.exceptions import ModbusException
import pytest

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_REGISTER_HOLDING,
    CONF_INPUT_TYPE,
    CONF_LAZY_ERROR,
    CONF_STATE_CLOSED,
    CONF_STATE_CLOSING,
    CONF_STATE_OPEN,
    CONF_STATE_OPENING,
    CONF_STATUS_REGISTER,
    CONF_STATUS_REGISTER_TYPE,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COVERS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
)
from homeassistant.core import State

from .conftest import TEST_ENTITY_NAME, ReadResult

ENTITY_ID = f"{COVER_DOMAIN}.{TEST_ENTITY_NAME}"


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_COVERS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_INPUT_TYPE: CALL_TYPE_COIL,
                }
            ]
        },
        {
            CONF_COVERS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                    CONF_SLAVE: 10,
                    CONF_SCAN_INTERVAL: 20,
                    CONF_LAZY_ERROR: 10,
                }
            ]
        },
    ],
)
async def test_config_cover(hass, mock_modbus):
    """Run configuration test for cover."""
    assert COVER_DOMAIN in hass.config.components


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_COVERS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_INPUT_TYPE: CALL_TYPE_COIL,
                    CONF_ADDRESS: 1234,
                    CONF_SLAVE: 1,
                },
            ],
        },
    ],
)
@pytest.mark.parametrize(
    "register_words,expected",
    [
        (
            [0x00],
            STATE_CLOSED,
        ),
        (
            [0x80],
            STATE_CLOSED,
        ),
        (
            [0xFE],
            STATE_CLOSED,
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
async def test_coil_cover(hass, expected, mock_do_cycle):
    """Run test for given config."""
    assert hass.states.get(ENTITY_ID).state == expected


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_COVERS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_SLAVE: 1,
                },
            ],
        },
    ],
)
@pytest.mark.parametrize(
    "register_words,expected",
    [
        (
            [0x00],
            STATE_CLOSED,
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
async def test_register_cover(hass, expected, mock_do_cycle):
    """Run test for given config."""
    assert hass.states.get(ENTITY_ID).state == expected


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_COVERS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_STATUS_REGISTER_TYPE: CALL_TYPE_REGISTER_HOLDING,
                }
            ]
        },
    ],
)
async def test_service_cover_update(hass, mock_modbus, mock_ha):
    """Run test for service homeassistant.update_entity."""
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_CLOSED
    mock_modbus.read_holding_registers.return_value = ReadResult([0x01])
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_OPEN


@pytest.mark.parametrize(
    "mock_test_state",
    [
        (State(ENTITY_ID, STATE_CLOSED),),
        (State(ENTITY_ID, STATE_CLOSING),),
        (State(ENTITY_ID, STATE_OPENING),),
        (State(ENTITY_ID, STATE_OPEN),),
    ],
    indirect=True,
)
@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_COVERS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_INPUT_TYPE: CALL_TYPE_COIL,
                    CONF_ADDRESS: 1234,
                    CONF_STATE_OPEN: 1,
                    CONF_STATE_CLOSED: 0,
                    CONF_STATE_OPENING: 2,
                    CONF_STATE_CLOSING: 3,
                    CONF_STATUS_REGISTER: 1234,
                    CONF_STATUS_REGISTER_TYPE: CALL_TYPE_REGISTER_HOLDING,
                    CONF_SCAN_INTERVAL: 0,
                }
            ]
        },
    ],
)
async def test_restore_state_cover(hass, mock_test_state, mock_modbus):
    """Run test for cover restore state."""
    test_state = mock_test_state[0].state
    assert hass.states.get(ENTITY_ID).state == test_state


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_COVERS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_STATUS_REGISTER_TYPE: CALL_TYPE_REGISTER_HOLDING,
                    CONF_SCAN_INTERVAL: 0,
                },
                {
                    CONF_NAME: f"{TEST_ENTITY_NAME}2",
                    CONF_INPUT_TYPE: CALL_TYPE_COIL,
                    CONF_ADDRESS: 1235,
                    CONF_SCAN_INTERVAL: 0,
                },
            ]
        },
    ],
)
async def test_service_cover_move(hass, mock_modbus, mock_ha):
    """Run test for service homeassistant.update_entity."""

    ENTITY_ID2 = f"{ENTITY_ID}2"
    mock_modbus.read_holding_registers.return_value = ReadResult([0x01])
    await hass.services.async_call(
        "cover", "open_cover", {"entity_id": ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_OPEN

    mock_modbus.read_holding_registers.return_value = ReadResult([0x00])
    await hass.services.async_call(
        "cover", "close_cover", {"entity_id": ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_CLOSED

    mock_modbus.reset()
    mock_modbus.read_holding_registers.side_effect = ModbusException("fail write_")
    await hass.services.async_call(
        "cover", "close_cover", {"entity_id": ENTITY_ID}, blocking=True
    )
    assert mock_modbus.read_holding_registers.called
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_modbus.read_coils.side_effect = ModbusException("fail write_")
    await hass.services.async_call(
        "cover", "close_cover", {"entity_id": ENTITY_ID2}, blocking=True
    )
    assert hass.states.get(ENTITY_ID2).state == STATE_UNAVAILABLE
