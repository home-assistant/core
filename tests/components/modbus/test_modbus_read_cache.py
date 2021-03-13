"""Test modbus read cache."""
from unittest import mock

import pytest

from homeassistant.components.modbus.modbus_read_cache import ModbusReadCache


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
