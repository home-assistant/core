"""Thetests for the Modbus sensor component."""
import pytest

from homeassistant.components.binary_sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CONF_INPUT_TYPE,
    CONF_LAZY_ERROR,
    CONF_SLAVE_COUNT,
    MODBUS_DOMAIN,
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
    STATE_UNKNOWN,
)
from homeassistant.core import State
from homeassistant.setup import async_setup_component

from .conftest import TEST_ENTITY_NAME, ReadResult, do_next_cycle

ENTITY_ID = f"{SENSOR_DOMAIN}.{TEST_ENTITY_NAME}".replace(" ", "_")


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
                    CONF_ADDRESS: 51,
                    CONF_INPUT_TYPE: CALL_TYPE_COIL,
                    CONF_SCAN_INTERVAL: 10,
                    CONF_LAZY_ERROR: 2,
                },
            ],
        },
    ],
)
@pytest.mark.parametrize(
    "register_words,do_exception,start_expect,end_expect",
    [
        (
            [0x00],
            True,
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ),
    ],
)
async def test_lazy_error_binary_sensor(hass, start_expect, end_expect, mock_do_cycle):
    """Run test for given config."""
    now = mock_do_cycle
    assert hass.states.get(ENTITY_ID).state == start_expect
    now = await do_next_cycle(hass, now, 11)
    assert hass.states.get(ENTITY_ID).state == start_expect
    now = await do_next_cycle(hass, now, 11)
    assert hass.states.get(ENTITY_ID).state == end_expect


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


ENTITY_ID2 = f"{ENTITY_ID}_1"


@pytest.mark.parametrize(
    "mock_test_state",
    [
        (
            State(ENTITY_ID, STATE_ON),
            State(ENTITY_ID2, STATE_OFF),
        )
    ],
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
                    CONF_SLAVE_COUNT: 1,
                }
            ]
        },
    ],
)
async def test_restore_state_binary_sensor(hass, mock_test_state, mock_modbus):
    """Run test for binary sensor restore state."""
    assert hass.states.get(ENTITY_ID).state == mock_test_state[0].state
    assert hass.states.get(ENTITY_ID2).state == mock_test_state[1].state


TEST_NAME = "test_sensor"


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 51,
                    CONF_SLAVE_COUNT: 3,
                }
            ]
        },
    ],
)
async def test_config_slave_binary_sensor(hass, mock_modbus):
    """Run config test for binary sensor."""
    assert SENSOR_DOMAIN in hass.config.components

    for addon in ["", " 1", " 2", " 3"]:
        entity_id = f"{SENSOR_DOMAIN}.{TEST_ENTITY_NAME}{addon}".replace(" ", "_")
        assert hass.states.get(entity_id) is not None


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
    ],
)
@pytest.mark.parametrize(
    "config_addon,register_words,expected, slaves",
    [
        (
            {CONF_SLAVE_COUNT: 1},
            [0x01],
            STATE_ON,
            [
                STATE_OFF,
            ],
        ),
        (
            {CONF_SLAVE_COUNT: 1},
            [0x02],
            STATE_OFF,
            [
                STATE_ON,
            ],
        ),
        (
            {CONF_SLAVE_COUNT: 1},
            [0x04],
            STATE_OFF,
            [
                STATE_OFF,
            ],
        ),
        (
            {CONF_SLAVE_COUNT: 7},
            [0x01],
            STATE_ON,
            [
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
            ],
        ),
        (
            {CONF_SLAVE_COUNT: 7},
            [0x82],
            STATE_OFF,
            [
                STATE_ON,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_ON,
            ],
        ),
        (
            {CONF_SLAVE_COUNT: 10},
            [0x01, 0x00],
            STATE_ON,
            [
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
            ],
        ),
        (
            {CONF_SLAVE_COUNT: 10},
            [0x01, 0x01],
            STATE_ON,
            [
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_ON,
                STATE_OFF,
                STATE_OFF,
            ],
        ),
        (
            {CONF_SLAVE_COUNT: 10},
            [0x81, 0x01],
            STATE_ON,
            [
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_OFF,
                STATE_ON,
                STATE_ON,
                STATE_OFF,
                STATE_OFF,
            ],
        ),
    ],
)
async def test_slave_binary_sensor(hass, expected, slaves, mock_do_cycle):
    """Run test for given config."""
    assert hass.states.get(ENTITY_ID).state == expected

    for i in range(len(slaves)):
        entity_id = f"{SENSOR_DOMAIN}.{TEST_ENTITY_NAME}_{i+1}".replace(" ", "_")
        assert hass.states.get(entity_id).state == slaves[i]


async def test_no_discovery_info_binary_sensor(hass, caplog):
    """Test setup without discovery info."""
    assert SENSOR_DOMAIN not in hass.config.components
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {"platform": MODBUS_DOMAIN}},
    )
    await hass.async_block_till_done()
    assert SENSOR_DOMAIN in hass.config.components
