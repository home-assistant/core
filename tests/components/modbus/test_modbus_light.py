"""The tests for the Modbus light component."""
import pytest

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_COILS,
    CONF_INPUT_TYPE,
    CONF_STATE_OFF,
    CONF_STATE_ON,
    CONF_VERIFY,
    CONF_WRITE_TYPE,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_LIGHTS,
    CONF_NAME,
    CONF_SLAVE,
    STATE_OFF,
    STATE_ON,
)

from .conftest import ReadResult, base_config_test, base_test, prepare_service_update


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_ADDRESS: 1234,
        },
        {
            CONF_ADDRESS: 1234,
            CONF_WRITE_TYPE: CALL_TYPE_COIL,
        },
        {
            CONF_ADDRESS: 1234,
            CONF_SLAVE: 1,
            CONF_COMMAND_OFF: 0x00,
            CONF_COMMAND_ON: 0x01,
            CONF_VERIFY: {
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                CONF_ADDRESS: 1235,
                CONF_STATE_OFF: 0,
                CONF_STATE_ON: 1,
            },
        },
        {
            CONF_ADDRESS: 1234,
            CONF_SLAVE: 1,
            CONF_COMMAND_OFF: 0x00,
            CONF_COMMAND_ON: 0x01,
            CONF_VERIFY: {
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
                CONF_ADDRESS: 1235,
                CONF_STATE_OFF: 0,
                CONF_STATE_ON: 1,
            },
        },
    ],
)
async def test_config_light(hass, do_config):
    """Run test for light."""
    device_name = "test_light"

    device_config = {
        CONF_NAME: device_name,
        **do_config,
    }

    await base_config_test(
        hass,
        device_config,
        device_name,
        LIGHT_DOMAIN,
        CONF_LIGHTS,
        None,
        method_discovery=True,
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
            STATE_ON,
        ),
        (
            [0x01],
            STATE_ON,
        ),
    ],
)
async def test_coil_light(hass, regs, expected):
    """Run test for given config."""
    light_name = "modbus_test_light"
    state = await base_test(
        hass,
        {
            CONF_NAME: light_name,
            CONF_ADDRESS: 1234,
            CONF_WRITE_TYPE: CALL_TYPE_COIL,
            CONF_VERIFY: {},
        },
        light_name,
        LIGHT_DOMAIN,
        CONF_LIGHTS,
        CONF_COILS,
        regs,
        expected,
        method_discovery=True,
        scan_interval=5,
    )
    assert state == expected


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
async def test_register_light(hass, regs, expected):
    """Run test for given config."""
    light_name = "modbus_test_light"
    state = await base_test(
        hass,
        {
            CONF_NAME: light_name,
            CONF_ADDRESS: 1234,
            CONF_SLAVE: 1,
            CONF_COMMAND_OFF: 0x00,
            CONF_COMMAND_ON: 0x01,
            CONF_VERIFY: {},
        },
        light_name,
        LIGHT_DOMAIN,
        CONF_LIGHTS,
        None,
        regs,
        expected,
        method_discovery=True,
        scan_interval=5,
    )
    assert state == expected


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
    ],
)
async def test_register_state_light(hass, regs, expected):
    """Run test for given config."""
    light_name = "modbus_test_light"
    state = await base_test(
        hass,
        {
            CONF_NAME: light_name,
            CONF_ADDRESS: 1234,
            CONF_SLAVE: 1,
            CONF_COMMAND_OFF: 0x04,
            CONF_COMMAND_ON: 0x40,
            CONF_VERIFY: {},
        },
        light_name,
        LIGHT_DOMAIN,
        CONF_LIGHTS,
        None,
        regs,
        expected,
        method_discovery=True,
        scan_interval=5,
    )
    assert state == expected


async def test_service_light_update(hass, mock_pymodbus):
    """Run test for service homeassistant.update_entity."""

    entity_id = "light.test"
    config = {
        CONF_LIGHTS: [
            {
                CONF_NAME: "test",
                CONF_ADDRESS: 1234,
                CONF_WRITE_TYPE: CALL_TYPE_COIL,
                CONF_VERIFY: {},
            }
        ]
    }
    mock_pymodbus.read_coils.return_value = ReadResult([0x01])
    await prepare_service_update(
        hass,
        config,
    )
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_ON
    mock_pymodbus.read_coils.return_value = ReadResult([0x00])
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_OFF
