"""The tests for the Modbus sensor component."""
from datetime import timedelta
import logging
from unittest import mock

import pytest

from homeassistant.components.modbus.const import (
    CALL_TYPE_REGISTER_INPUT,
    CONF_REGISTER,
    CONF_REGISTER_TYPE,
    CONF_REGISTERS,
    DEFAULT_HUB,
    MODBUS_DOMAIN as DOMAIN,
)
from homeassistant.const import CONF_NAME, CONF_PLATFORM, CONF_SCAN_INTERVAL
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockModule, async_fire_time_changed, mock_integration

_LOGGER = logging.getLogger(__name__)


@pytest.fixture()
def mock_hub(hass):
    """Mock hub."""
    mock_integration(hass, MockModule(DOMAIN))
    hub = mock.MagicMock()
    hub.name = "hub"
    hass.data[DOMAIN] = {DEFAULT_HUB: hub}
    return hub


class ReadResult:
    """Storage class for register read results."""

    def __init__(self, register_words):
        """Init."""
        self.registers = register_words


async def run_test(
    hass, use_mock_hub, register_config, entity_domain, register_words, expected
):
    """Run test for given config and check that sensor outputs expected result."""

    # Full sensor configuration
    sensor_name = "modbus_test_sensor"
    scan_interval = 5
    config = {
        entity_domain: {
            CONF_PLATFORM: "modbus",
            CONF_SCAN_INTERVAL: scan_interval,
            CONF_REGISTERS: [
                dict(**{CONF_NAME: sensor_name, CONF_REGISTER: 1234}, **register_config)
            ],
        }
    }

    # Setup inputs for the sensor
    read_result = ReadResult(register_words)
    if register_config.get(CONF_REGISTER_TYPE) == CALL_TYPE_REGISTER_INPUT:
        use_mock_hub.read_input_registers.return_value = read_result
    else:
        use_mock_hub.read_holding_registers.return_value = read_result

    # Initialize sensor
    now = dt_util.utcnow()
    with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
        assert await async_setup_component(hass, entity_domain, config)

    # Trigger update call with time_changed event
    now += timedelta(seconds=scan_interval + 1)
    with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()

    # Check state
    entity_id = f"{entity_domain}.{sensor_name}"
    state = hass.states.get(entity_id).state
    assert state == expected
