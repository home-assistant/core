"""The tests for the Modbus sensor component."""
from datetime import timedelta
import logging
from unittest import mock

import pytest

from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CALL_TYPE_REGISTER_INPUT,
    DEFAULT_HUB,
    MODBUS_DOMAIN as DOMAIN,
)
from homeassistant.const import CONF_PLATFORM, CONF_SCAN_INTERVAL
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
        self.bits = register_words


async def run_base_test(
    sensor_name,
    hass,
    use_mock_hub,
    data_array,
    register_type,
    entity_domain,
    register_words,
    expected,
):
    """Run test for given config."""

    # Full sensor configuration
    scan_interval = 5
    config = {
        entity_domain: {
            CONF_PLATFORM: "modbus",
            CONF_SCAN_INTERVAL: scan_interval,
            **data_array,
        }
    }

    # Setup inputs for the sensor
    read_result = ReadResult(register_words)
    if register_type == CALL_TYPE_COIL:
        use_mock_hub.read_coils.return_value = read_result
    elif register_type == CALL_TYPE_DISCRETE:
        use_mock_hub.read_discrete_inputs.return_value = read_result
    elif register_type == CALL_TYPE_REGISTER_INPUT:
        use_mock_hub.read_input_registers.return_value = read_result
    else:  # CALL_TYPE_REGISTER_HOLDING
        use_mock_hub.read_holding_registers.return_value = read_result

    # Initialize sensor
    now = dt_util.utcnow()
    with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
        assert await async_setup_component(hass, entity_domain, config)
        await hass.async_block_till_done()

    # Trigger update call with time_changed event
    now += timedelta(seconds=scan_interval + 1)
    with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()
