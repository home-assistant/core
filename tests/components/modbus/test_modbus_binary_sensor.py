"""The tests for the Modbus sensor component."""
import pytest

from homeassistant.components.binary_sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CONF_INPUT_TYPE,
    CONF_INPUTS,
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

from .conftest import ReadResult, base_config_test, base_test, run_service_update


@pytest.mark.parametrize("do_discovery", [False, True])
@pytest.mark.parametrize(
    "do_options",
    [
        {},
        {
            CONF_SLAVE: 10,
            CONF_INPUT_TYPE: CALL_TYPE_DISCRETE,
            CONF_DEVICE_CLASS: "door",
        },
    ],
)
async def test_config_binary_sensor(hass, do_discovery, do_options):
    """Run test for binary sensor."""
    sensor_name = "test_sensor"
    config_sensor = {
        CONF_NAME: sensor_name,
        CONF_ADDRESS: 51,
        **do_options,
    }
    await base_config_test(
        hass,
        config_sensor,
        sensor_name,
        SENSOR_DOMAIN,
        CONF_BINARY_SENSORS,
        CONF_INPUTS,
        method_discovery=do_discovery,
    )


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
    sensor_name = "modbus_test_binary_sensor"
    state = await base_test(
        hass,
        {CONF_NAME: sensor_name, CONF_ADDRESS: 1234, CONF_INPUT_TYPE: do_type},
        sensor_name,
        SENSOR_DOMAIN,
        CONF_BINARY_SENSORS,
        CONF_INPUTS,
        regs,
        expected,
        method_discovery=True,
        scan_interval=5,
    )
    assert state == expected


async def test_service_binary_sensor_update(hass, mock_pymodbus):
    """Run test for service homeassistant.update_entity."""

    entity_id = "binary_sensor.test"
    config = {
        CONF_BINARY_SENSORS: [
            {
                CONF_NAME: "test",
                CONF_ADDRESS: 1234,
                CONF_INPUT_TYPE: CALL_TYPE_COIL,
            }
        ]
    }
    mock_pymodbus.read_coils.return_value = ReadResult([0x00])
    await run_service_update(
        hass,
        config,
        entity_id,
    )
    assert hass.states.get(entity_id).state == STATE_OFF
    mock_pymodbus.read_coils.return_value = ReadResult([0x01])
    await run_service_update(
        hass,
        config,
        entity_id,
    )
    assert hass.states.get(entity_id).state == STATE_ON
