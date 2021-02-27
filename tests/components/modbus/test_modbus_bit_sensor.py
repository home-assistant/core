"""The tests for the Modbus sensor component."""
from collections import namedtuple
from unittest import mock

from pymodbus.exceptions import ConnectionException, ModbusException
import pytest

from homeassistant.components.binary_sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.modbus.bit_sensor import (
    ModbusReadCache,
    setup_bit_sensors,
)
from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_BIT_NUMBER,
    CONF_BIT_SENSORS,
    CONF_INPUT_TYPE,
    CONF_INPUTS,
)
from homeassistant.components.modbus.modbus import ModbusHub
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COUNT,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SLAVE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers.restore_state import RestoreEntity

from .conftest import base_config_test, base_test


@pytest.mark.parametrize(
    "discovery_info,call_count",
    [
        (None, 0),
        (
            {
                CONF_BIT_SENSORS: [
                    {CONF_COUNT: 1, CONF_BIT_NUMBER: 16, CONF_NAME: "test"}
                ]
            },
            1,
        ),
    ],
)
@mock.patch("homeassistant.components.modbus.bit_sensor._LOGGER")
def test_setup_bit_sensors(mock_logger, discovery_info, call_count):
    """Test setup bit sensor."""
    setup_bit_sensors(mock.MagicMock(), discovery_info)
    assert mock_logger.error.call_count == call_count


@pytest.mark.parametrize(
    "method_discovery, do_config",
    [
        (
            True,
            {
                CONF_ADDRESS: 51,
                CONF_BIT_NUMBER: 5,
            },
        ),
        (
            True,
            {
                CONF_ADDRESS: 51,
                CONF_COUNT: 1,
                CONF_BIT_NUMBER: 17,
            },
        ),
        (
            True,
            {
                CONF_ADDRESS: 51,
                CONF_BIT_NUMBER: 5,
                CONF_SLAVE: 10,
                CONF_COUNT: 1,
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                CONF_DEVICE_CLASS: "battery",
            },
        ),
        (
            True,
            {
                CONF_ADDRESS: 51,
                CONF_BIT_NUMBER: 5,
                CONF_SLAVE: 10,
                CONF_COUNT: 1,
                CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
                CONF_DEVICE_CLASS: "battery",
            },
        ),
        (
            False,
            {
                CONF_ADDRESS: 51,
                CONF_INPUT_TYPE: CALL_TYPE_COIL,
                CONF_SLAVE: 10,
                CONF_DEVICE_CLASS: "battery",
            },
        ),
    ],
)
async def test_config_sensor(hass, method_discovery, do_config):
    """Run test for sensor."""
    sensor_name = "test_sensor"
    config_sensor = {
        CONF_NAME: sensor_name,
        **do_config,
    }
    await base_config_test(
        hass,
        config_sensor,
        sensor_name,
        SENSOR_DOMAIN,
        CONF_BIT_SENSORS,
        CONF_INPUTS,
        method_discovery=method_discovery,
    )


@pytest.mark.parametrize(
    "cfg,regs,expected",
    [
        (
            {},
            [0],
            STATE_OFF,
        ),
        (
            {},
            ModbusException("Modbus Exception"),
            STATE_UNAVAILABLE,
        ),
        (
            {},
            [0x20],
            STATE_ON,
        ),
        (
            {},
            [0xFF],
            STATE_ON,
        ),
        (
            {},
            [0xDF],
            STATE_OFF,
        ),
        (
            {CONF_BIT_NUMBER: 15},
            [0x8000],
            STATE_ON,
        ),
        (
            {CONF_BIT_NUMBER: 15},
            [0x7FFF],
            STATE_OFF,
        ),
        (
            {CONF_BIT_NUMBER: 31, CONF_COUNT: 2},
            [0x0000, 0x8000],
            STATE_ON,
        ),
        (
            {CONF_BIT_NUMBER: 63, CONF_COUNT: 4},
            [0x0000, 0x0000, 0x0000, 0x8000],
            STATE_ON,
        ),
        (
            {CONF_BIT_NUMBER: 28, CONF_COUNT: 4},
            [0x0000, 0x1000, 0x0000, 0x0000],
            STATE_ON,
        ),
    ],
)
async def test_all_bit_sensor(hass, cfg, regs, expected):
    """Run test for sensor."""
    sensor_name = "modbus_test_sensor"
    state = await base_test(
        hass,
        {
            CONF_NAME: sensor_name,
            CONF_ADDRESS: 1234,
            CONF_BIT_NUMBER: 5,
            **cfg,
        },
        sensor_name,
        SENSOR_DOMAIN,
        CONF_BIT_SENSORS,
        CONF_INPUTS,
        regs,
        expected,
        method_discovery=True,
        scan_interval=5,
    )
    assert state == expected


Registers = namedtuple("Registers", ["registers"])


@pytest.mark.parametrize(
    "read_data,last_state,expected",
    [
        (ConnectionException("Modbus Exception"), STATE_ON, STATE_UNAVAILABLE),
        (
            lambda _1, _2, _3: Registers([0x00]),
            STATE_ON,
            STATE_OFF,
        ),
        (
            lambda _1, _2, _3: Registers([0xFF]),
            STATE_OFF,
            STATE_ON,
        ),
    ],
)
@mock.patch.object(ModbusHub, "read_holding_registers")
async def test_register_sensor_last_state(
    mock_read, hass, read_data, last_state, expected
):
    """Run test for given config."""
    mock_read.side_effect = read_data
    switch_name = "modbus_test_switch"

    with mock.patch.object(RestoreEntity, "async_get_last_state") as last_state_mock:
        last_state_mock.return_value = mock.MagicMock()
        last_state_mock.return_value.state = last_state
        state = await base_test(
            hass,
            {
                CONF_NAME: switch_name,
                CONF_ADDRESS: 1234,
                CONF_BIT_NUMBER: 5,
            },
            switch_name,
            SENSOR_DOMAIN,
            CONF_BIT_SENSORS,
            CONF_INPUTS,
            [0x00],
            STATE_UNAVAILABLE,
            method_discovery=True,
            scan_interval=5,
        )
        assert state == expected


@pytest.fixture
def hub():
    """Hub fixture."""
    return mock.MagicMock()


@pytest.fixture
def cache(hub):
    """Cache fixture."""
    return ModbusReadCache(hub)


@mock.patch("time.time", return_value=1)
def test_consecutive_calls(_, cache, hub):
    """Test consecutive calls reads only once."""

    # First register read, put the value in the cache
    hub.read_holding_registers.return_value = [0]
    assert cache.read_holding_registers(50, 70, 1) == [0]

    # update an actual value after the first read
    hub.read_holding_registers.return_value = [1]

    # should keep reading old value from the cache
    assert cache.read_holding_registers(50, 70, 1) == [0]
    assert cache.read_holding_registers(50, 70, 1) == [0]

    # underlying hub.read_holding_registers should be called only once
    assert hub.read_holding_registers.call_count == 1
    # .. with the correct input arguments
    hub.read_holding_registers.assert_called_once_with(50, 70, 1)

    # make a second call with the extra named argument, read the updated value
    assert cache.read_holding_registers(50, 70, 1, extra=1) == [1]

    # expect 2 calls to the hub method
    assert hub.read_holding_registers.call_count == 2
    hub.read_holding_registers.assert_called_with(50, 70, 1, extra=1)


@mock.patch("time.time")
def test_cache_expire_in_one_second(mock_time, cache, hub):
    """Test consecutive reads made one second apart ignore the cache."""
    hub.read_holding_registers.return_value = [0]

    current_time = 1615633800.799
    mock_time.return_value = current_time

    assert cache.read_holding_registers(50, 70, 1) == [0]

    # update an actual value after the first read
    hub.read_holding_registers.return_value = [1]
    assert cache.read_holding_registers(50, 70, 1) == [0]

    # read at the same time, should use cached value
    assert hub.read_holding_registers.call_count == 1

    # advance current time to 200ms, should still use cached value
    mock_time.return_value = current_time + 0.2
    assert cache.read_holding_registers(50, 70, 1) == [0]
    assert cache.read_holding_registers(50, 70, 1) == [0]
    assert hub.read_holding_registers.call_count == 1

    # advance current time to 1000ms, should read a new value from the hub
    mock_time.return_value = current_time + 1.0
    assert cache.read_holding_registers(50, 70, 1) == [1]
    assert hub.read_holding_registers.call_count == 2


def test_pass_through_non_cached(cache, hub):
    """Test non cached calls works as usual."""
    hub.write_holding_registers.return_value = [0]
    assert cache.write_holding_registers(50, 70, 1) == [0]

    hub.write_holding_registers.return_value = [1]
    assert cache.write_holding_registers(50, 70, 1) == [1]

    hub.write_holding_registers.return_value = [2]
    assert cache.write_holding_registers(50, 70, 1) == [2]

    # no caching involved
    assert hub.write_holding_registers.call_count == 3
    hub.write_holding_registers.assert_called_with(50, 70, 1)
