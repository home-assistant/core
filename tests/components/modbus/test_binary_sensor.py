"""Thetests for the Modbus sensor component."""
import pytest

from homeassistant.components.binary_sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CONF_INPUT_TYPE,
    CONF_LAZY_ERROR,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BINARY_SENSORS,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import State

from .conftest import TEST_ENTITY_NAME, ReadResult

ENTITY_ID = f"{SENSOR_DOMAIN}.{TEST_ENTITY_NAME}"


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                }
            ]
        },
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_SLAVE: 10,
                    CONF_INPUT_TYPE: CALL_TYPE_DISCRETE,
                    CONF_DEVICE_CLASS: "door",
                    CONF_LAZY_ERROR: 10,
                }
            ]
        },
    ],
)
async def test_config_binary_sensor(hass, mock_modbus):
    """Run config test for binary sensor."""
    assert SENSOR_DOMAIN in hass.config.components


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_INPUT_TYPE: CALL_TYPE_COIL,
                },
            ],
        },
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_INPUT_TYPE: CALL_TYPE_DISCRETE,
                },
            ],
        },
    ],
)
@pytest.mark.parametrize(
    "register_words,do_exception,expected",
    [
        (
            [0xFF],
            False,
            STATE_ON,
        ),
        (
            [0x01],
            False,
            STATE_ON,
        ),
        (
            [0x00],
            False,
            STATE_OFF,
        ),
        (
            [0x80],
            False,
            STATE_OFF,
        ),
        (
            [0xFE],
            False,
            STATE_OFF,
        ),
        (
            [0x00],
            True,
            STATE_UNAVAILABLE,
        ),
    ],
)
async def test_all_binary_sensor(hass, expected, mock_do_cycle):
    """Run test for given config."""
    assert hass.states.get(ENTITY_ID).state == expected


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_INPUT_TYPE: CALL_TYPE_COIL,
                }
            ]
        },
    ],
)
async def test_service_binary_sensor_update(hass, mock_modbus, mock_ha):
    """Run test for service homeassistant.update_entity."""

    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": ENTITY_ID}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    mock_modbus.read_coils.return_value = ReadResult([0x01])
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": ENTITY_ID}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON


@pytest.mark.parametrize(
    "mock_test_state",
    [(State(ENTITY_ID, STATE_ON),)],
    indirect=True,
)
@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_SCAN_INTERVAL: 0,
                }
            ]
        },
    ],
)
async def test_restore_state_binary_sensor(hass, mock_test_state, mock_modbus):
    """Run test for binary sensor restore state."""
    assert hass.states.get(ENTITY_ID).state == mock_test_state[0].state
