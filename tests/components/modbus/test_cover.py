"""The tests for the Modbus cover component."""
from freezegun.api import FrozenDateTimeFactory
from pymodbus.exceptions import ModbusException
import pytest

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_REGISTER_HOLDING,
    CONF_DEVICE_ADDRESS,
    CONF_INPUT_TYPE,
    CONF_LAZY_ERROR,
    CONF_STATE_CLOSED,
    CONF_STATE_CLOSING,
    CONF_STATE_OPEN,
    CONF_STATE_OPENING,
    CONF_STATUS_REGISTER,
    CONF_STATUS_REGISTER_TYPE,
    MODBUS_DOMAIN,
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
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component

from .conftest import TEST_ENTITY_NAME, ReadResult, do_next_cycle

ENTITY_ID = f"{COVER_DOMAIN}.{TEST_ENTITY_NAME}".replace(" ", "_")
ENTITY_ID2 = f"{ENTITY_ID}_2"


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
        {
            CONF_COVERS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                    CONF_DEVICE_ADDRESS: 10,
                    CONF_SCAN_INTERVAL: 20,
                    CONF_LAZY_ERROR: 10,
                }
            ]
        },
    ],
)
async def test_config_cover(hass: HomeAssistant, mock_modbus) -> None:
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
    ("register_words", "expected"),
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
async def test_coil_cover(hass: HomeAssistant, expected, mock_do_cycle) -> None:
    """Run test for given config."""
    assert hass.states.get(ENTITY_ID).state == expected


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
                    CONF_SCAN_INTERVAL: 10,
                    CONF_LAZY_ERROR: 2,
                },
            ],
        },
    ],
)
@pytest.mark.parametrize(
    ("register_words", "do_exception", "start_expect", "end_expect"),
    [
        (
            [0x00],
            True,
            STATE_OPEN,
            STATE_UNAVAILABLE,
        ),
    ],
)
async def test_lazy_error_cover(
    hass: HomeAssistant, start_expect, end_expect, mock_do_cycle: FrozenDateTimeFactory
) -> None:
    """Run test for given config."""
    assert hass.states.get(ENTITY_ID).state == start_expect
    await do_next_cycle(hass, mock_do_cycle, 11)
    assert hass.states.get(ENTITY_ID).state == start_expect
    await do_next_cycle(hass, mock_do_cycle, 11)
    assert hass.states.get(ENTITY_ID).state == end_expect


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
    ("register_words", "expected"),
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
async def test_register_cover(hass: HomeAssistant, expected, mock_do_cycle) -> None:
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
async def test_service_cover_update(hass: HomeAssistant, mock_modbus, mock_ha) -> None:
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
async def test_restore_state_cover(
    hass: HomeAssistant, mock_test_state, mock_modbus
) -> None:
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
                    CONF_NAME: f"{TEST_ENTITY_NAME} 2",
                    CONF_INPUT_TYPE: CALL_TYPE_COIL,
                    CONF_ADDRESS: 1235,
                    CONF_SCAN_INTERVAL: 0,
                },
            ]
        },
    ],
)
async def test_service_cover_move(hass: HomeAssistant, mock_modbus, mock_ha) -> None:
    """Run test for service homeassistant.update_entity."""

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


async def test_no_discovery_info_cover(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup without discovery info."""
    assert COVER_DOMAIN not in hass.config.components
    assert await async_setup_component(
        hass,
        COVER_DOMAIN,
        {COVER_DOMAIN: {"platform": MODBUS_DOMAIN}},
    )
    await hass.async_block_till_done()
    assert COVER_DOMAIN in hass.config.components
