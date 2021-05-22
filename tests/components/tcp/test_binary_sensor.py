"""The tests for the TCP binary sensor platform."""
from datetime import timedelta
from unittest.mock import call, patch

import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import assert_setup_component, async_fire_time_changed
import tests.components.tcp.test_sensor as test_tcp

BINARY_SENSOR_CONFIG = test_tcp.TEST_CONFIG["sensor"]
TEST_CONFIG = {"binary_sensor": BINARY_SENSOR_CONFIG}
TEST_ENTITY = "binary_sensor.test_name"


@pytest.fixture(name="mock_socket")
def mock_socket_fixture():
    """Mock the socket."""
    with patch(
        "homeassistant.components.tcp.sensor.socket.socket"
    ) as mock_socket, patch(
        "homeassistant.components.tcp.sensor.select.select",
        return_value=(True, False, False),
    ):
        # yield the return value of the socket context manager
        yield mock_socket.return_value.__enter__.return_value


@pytest.fixture
def now():
    """Return datetime UTC now."""
    return utcnow()


async def test_setup_platform_valid_config(hass, mock_socket):
    """Check a valid configuration."""
    with assert_setup_component(1, "binary_sensor"):
        assert await async_setup_component(hass, "binary_sensor", TEST_CONFIG)
        await hass.async_block_till_done()


async def test_setup_platform_invalid_config(hass, mock_socket):
    """Check the invalid configuration."""
    with assert_setup_component(0):
        assert await async_setup_component(
            hass,
            "binary_sensor",
            {"binary_sensor": {"platform": "tcp", "porrt": 1234}},
        )
        await hass.async_block_till_done()


async def test_state(hass, mock_socket, now):
    """Check the state and update of the binary sensor."""
    mock_socket.recv.return_value = b"off"
    assert await async_setup_component(hass, "binary_sensor", TEST_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY)

    assert state
    assert state.state == STATE_OFF
    assert mock_socket.connect.called
    assert mock_socket.connect.call_args == call(
        (BINARY_SENSOR_CONFIG["host"], BINARY_SENSOR_CONFIG["port"])
    )
    assert mock_socket.send.called
    assert mock_socket.send.call_args == call(BINARY_SENSOR_CONFIG["payload"].encode())
    assert mock_socket.recv.called
    assert mock_socket.recv.call_args == call(BINARY_SENSOR_CONFIG["buffer_size"])

    mock_socket.recv.return_value = b"on"

    async_fire_time_changed(hass, now + timedelta(seconds=45))
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY)

    assert state
    assert state.state == STATE_ON
