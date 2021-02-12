"""The tests for the Modbus sensor component."""
from datetime import timedelta
import logging
from unittest import mock

import pytest

from homeassistant.components.modbus.const import DEFAULT_HUB, MODBUS_DOMAIN as DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
)
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


class ReadResult:
    """Storage class for register read results."""

    def __init__(self, register_words):
        """Init."""
        self.registers = register_words
        self.bits = register_words


async def base_test(
    sensor_name,
    hass,
    data_array,
    entity_domain,
    scan_interval,
    register_words,
    expected,
    method_discovery=False,
):
    """Run test on device for given config."""

    # Full sensor configuration
    if method_discovery:
        config = {
            DOMAIN: {
                CONF_NAME: DEFAULT_HUB,
                CONF_TYPE: "tcp",
                CONF_HOST: "modbusTest",
                CONF_PORT: 5001,
                **data_array,
            },
        }
    else:
        config = {
            DOMAIN: {
                CONF_NAME: DEFAULT_HUB,
                CONF_TYPE: "tcp",
                CONF_HOST: "modbusTest",
                CONF_PORT: 5001,
            },
        }
        configDeviceOLD = {
            entity_domain: {
                CONF_PLATFORM: DOMAIN,
                CONF_SCAN_INTERVAL: scan_interval,
                **data_array,
            }
        }

    mock_sync = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_sync
    ), mock.patch(
        "homeassistant.components.modbus.modbus.ModbusSerialClient",
        return_value=mock_sync,
    ), mock.patch(
        "homeassistant.components.modbus.modbus.ModbusUdpClient", return_value=mock_sync
    ):

        # Setup inputs for the sensor
        read_result = ReadResult(register_words)
        mock_sync.read_coils.return_value = read_result
        mock_sync.read_discrete_inputs.return_value = read_result
        mock_sync.read_input_registers.return_value = read_result
        mock_sync.read_holding_registers.return_value = read_result

        # mock timer and add modbus platform with devices (new config)
        now = dt_util.utcnow()
        with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
            # setup modbus platform
            if method_discovery:
                await async_load_platform(
                    hass, entity_domain, DOMAIN, config[DOMAIN], config
                )
            else:
                # first add modbus platform using old config
                assert await async_setup_component(hass, DOMAIN, config)
                await hass.async_block_till_done()

                # setup component old style
                assert await async_setup_component(
                    hass,
                    entity_domain,
                    configDeviceOLD,
                )

            await hass.async_block_till_done()

        entity_id = f"{entity_domain}.{sensor_name}"
        device = hass.states.get(entity_id)
        if device is None:
            pytest.fail("CONFIG failed, see output")

        # Trigger update call with time_changed event
        now = now + timedelta(seconds=scan_interval + 1)
        with mock.patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
            async_fire_time_changed(hass, now)
            await hass.async_block_till_done()

        # Check state
        state = hass.states.get(entity_id).state
        assert state == expected
