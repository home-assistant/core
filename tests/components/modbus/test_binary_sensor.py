"""The tests for the Modbus sensor component."""
import pytest

from homeassistant.components.binary_sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CONF_INPUT_TYPE,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BINARY_SENSORS,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SLAVE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import State

from .conftest import ReadResult, base_test, prepare_service_update

sensor_name = "test_binary_sensor"
entity_id = f"{SENSOR_DOMAIN}.{sensor_name}"


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: sensor_name,
                    CONF_ADDRESS: 51,
                }
            ]
        },
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: sensor_name,
                    CONF_ADDRESS: 51,
                    CONF_SLAVE: 10,
                    CONF_INPUT_TYPE: CALL_TYPE_DISCRETE,
                    CONF_DEVICE_CLASS: "door",
                }
            ]
        },
    ],
)
async def test_config_binary_sensor(hass, mock_modbus):
    """Run config test for binary sensor."""
    assert SENSOR_DOMAIN in hass.config.components


@pytest.mark.parametrize("do_type", [CALL_TYPE_COIL, CALL_TYPE_DISCRETE])
@pytest.mark.parametrize(
    "regs,expected",
    [
        (
            [0xFF],
            STATE_ON,
        ),
        (
            [0x01],
            STATE_ON,
        ),
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
            None,
            STATE_UNAVAILABLE,
        ),
    ],
)
async def test_all_binary_sensor(hass, do_type, regs, expected):
    """Run test for given config."""
    state = await base_test(
        hass,
        {CONF_NAME: sensor_name, CONF_ADDRESS: 1234, CONF_INPUT_TYPE: do_type},
        sensor_name,
        SENSOR_DOMAIN,
        CONF_BINARY_SENSORS,
        None,
        regs,
        expected,
        method_discovery=True,
        scan_interval=5,
    )
    assert state == expected


async def test_service_binary_sensor_update(hass, mock_pymodbus):
    """Run test for service homeassistant.update_entity."""

    config = {
        CONF_BINARY_SENSORS: [
            {
                CONF_NAME: sensor_name,
                CONF_ADDRESS: 1234,
                CONF_INPUT_TYPE: CALL_TYPE_COIL,
            }
        ]
    }
    mock_pymodbus.read_coils.return_value = ReadResult([0x00])
    await prepare_service_update(
        hass,
        config,
    )
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    mock_pymodbus.read_coils.return_value = ReadResult([0x01])
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_ON


@pytest.mark.parametrize(
    "mock_test_state",
    [(State(entity_id, STATE_ON),)],
    indirect=True,
)
@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_BINARY_SENSORS: [
                {
                    CONF_NAME: sensor_name,
                    CONF_ADDRESS: 51,
                }
            ]
        },
    ],
)
async def test_restore_state_binary_sensor(hass, mock_test_state, mock_modbus):
    """Run test for binary sensor restore state."""
    assert hass.states.get(entity_id).state == mock_test_state[0].state
