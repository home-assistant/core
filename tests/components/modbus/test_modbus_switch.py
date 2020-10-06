"""The tests for the Modbus switch component."""
from datetime import timedelta
import logging

from homeassistant.components.modbus.const import CALL_TYPE_COIL, CONF_COILS
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import CONF_NAME, CONF_SLAVE

from .conftest import run_base_read_test, setup_base_test

_LOGGER = logging.getLogger(__name__)


async def run_sensor_test(hass, use_mock_hub, value, expected):
    """Run test for given config."""
    switch_name = "modbus_test_switch"
    scan_interval = 5
    entity_id, now, device = await setup_base_test(
        switch_name,
        hass,
        use_mock_hub,
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
        use_mock_hub,
        CALL_TYPE_COIL,
        value,
        expected,
        now + timedelta(seconds=scan_interval + 1),
    )


async def test_read_coil_false(hass, mock_hub):
    """Test reading of switch coil."""
    await run_sensor_test(
        hass,
        mock_hub,
        [0x00],
        expected="off",
    )


async def test_read_coil_true(hass, mock_hub):
    """Test reading of switch coil."""
    await run_sensor_test(
        hass,
        mock_hub,
        [0xFF],
        expected="on",
    )
