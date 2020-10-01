"""The tests for the Modbus sensor component."""
from datetime import timedelta
import logging

from homeassistant.components.binary_sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CONF_ADDRESS,
    CONF_INPUT_TYPE,
    CONF_INPUTS,
)
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON

from .conftest import run_base_read_test, setup_base_test

_LOGGER = logging.getLogger(__name__)


async def run_sensor_test(hass, use_mock_hub, register_config, value, expected):
    """Run test for given config."""
    sensor_name = "modbus_test_binary_sensor"
    scan_interval = 5
    entity_id, now, device = await setup_base_test(
        sensor_name,
        hass,
        use_mock_hub,
        {
            CONF_INPUTS: [
                dict(**{CONF_NAME: sensor_name, CONF_ADDRESS: 1234}, **register_config)
            ]
        },
        SENSOR_DOMAIN,
        scan_interval,
    )
    await run_base_read_test(
        entity_id,
        hass,
        use_mock_hub,
        register_config.get(CONF_INPUT_TYPE),
        value,
        expected,
        now + timedelta(seconds=scan_interval + 1),
    )


async def test_coil_true(hass, mock_hub):
    """Test conversion of single word register."""
    register_config = {
        CONF_INPUT_TYPE: CALL_TYPE_COIL,
    }
    await run_sensor_test(
        hass,
        mock_hub,
        register_config,
        [0xFF],
        STATE_ON,
    )


async def test_coil_false(hass, mock_hub):
    """Test conversion of single word register."""
    register_config = {
        CONF_INPUT_TYPE: CALL_TYPE_COIL,
    }
    await run_sensor_test(
        hass,
        mock_hub,
        register_config,
        [0x00],
        STATE_OFF,
    )


async def test_discrete_true(hass, mock_hub):
    """Test conversion of single word register."""
    register_config = {
        CONF_INPUT_TYPE: CALL_TYPE_DISCRETE,
    }
    await run_sensor_test(
        hass,
        mock_hub,
        register_config,
        [0xFF],
        expected="on",
    )


async def test_discrete_false(hass, mock_hub):
    """Test conversion of single word register."""
    register_config = {
        CONF_INPUT_TYPE: CALL_TYPE_DISCRETE,
    }
    await run_sensor_test(
        hass,
        mock_hub,
        register_config,
        [0x00],
        expected="off",
    )
