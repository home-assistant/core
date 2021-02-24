"""The tests for the Modbus sensor component."""
from unittest import mock
from unittest.mock import patch

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

from tests.common import async_fire_time_changed


@pytest.fixture()
def mock_hub(hass):
    """Mock hub."""
    with patch("homeassistant.components.modbus.setup", return_value=True):
        hub = mock.MagicMock()
        hub.name = "hub"
        hass.data[DOMAIN] = {DEFAULT_HUB: hub}
        yield hub


class ReadResult:
    """Storage class for register read results."""

    def __init__(self, register_words):
        """Init."""
        self.registers = register_words
        self.bits = register_words


async def setup_base_test(
    sensor_name,
    hass,
    use_mock_hub,
    data_array,
    entity_domain,
    scan_interval,
):
    """Run setup device for given config."""

    # Full sensor configuration
    config = {
        entity_domain: {
            CONF_PLATFORM: "modbus",
            CONF_SCAN_INTERVAL: scan_interval,
            **data_array,
        }
    }

    # Initialize sensor
    now = dt_util.utcnow()
    with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
        assert await async_setup_component(hass, entity_domain, config)
        await hass.async_block_till_done()

    entity_id = f"{entity_domain}.{sensor_name}"
    device = hass.states.get(entity_id)
    if device is None:
        pytest.fail("CONFIG failed, see output")
    return entity_id, now, device


async def run_base_read_test(
    entity_id,
    hass,
    use_mock_hub,
    register_type,
    register_words,
    expected,
    now,
):
    """Run test for given config."""

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

    # Trigger update call with time_changed event
    with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()

    # Check state
    state = hass.states.get(entity_id).state
    assert state == expected
