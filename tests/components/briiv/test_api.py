"""Tests for the Briiv API."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.briiv.api import BriivAPI, BriivCommands, BriivError


@pytest.fixture
def mock_socket():
    """Mock socket creation."""
    with patch("socket.socket") as mock_sock:
        mock_sock.return_value.getsockname.return_value = ("127.0.0.1", 3334)
        yield mock_sock


@pytest.fixture
def mock_loop():
    """Mock asyncio loop."""
    return AsyncMock()


async def test_api_initialization() -> None:
    """Test API initialization."""
    api = BriivAPI(host="192.168.1.100", port=3334, serial_number="TEST123")
    assert api.host == "192.168.1.100"
    assert api.port == 3334
    assert api.serial_number == "TEST123"
    assert api.callbacks == []


async def test_send_command(mock_socket, mock_loop) -> None:
    """Test sending commands."""
    api = BriivAPI(serial_number="TEST123")
    api._shared_socket = mock_socket.return_value

    command = BriivCommands.power_command("TEST123", True)
    await api.send_command(command)

    # Verify socket sent correct data
    sent_data = json.dumps(command).encode()
    mock_socket.return_value.sendto.assert_called_once()
    call_args = mock_socket.return_value.sendto.call_args[0]
    assert call_args[0] == sent_data


async def test_set_power() -> None:
    """Test setting power state."""
    api = BriivAPI(serial_number="TEST123")
    api.send_command = AsyncMock()

    await api.set_power(True)
    api.send_command.assert_called_once()
    command = api.send_command.call_args[0][0]
    assert command["command"] == "power"
    assert command["power"] == 1


async def test_set_fan_speed() -> None:
    """Test setting fan speed."""
    api = BriivAPI(serial_number="TEST123")
    api.send_command = AsyncMock()

    await api.set_fan_speed(50)
    api.send_command.assert_called_once()
    command = api.send_command.call_args[0][0]
    assert command["command"] == "fan_speed"
    assert command["fan_speed"] == 50


async def test_set_boost() -> None:
    """Test setting boost mode."""
    api = BriivAPI(serial_number="TEST123")
    api.send_command = AsyncMock()

    await api.set_boost(True)
    api.send_command.assert_called_once()
    command = api.send_command.call_args[0][0]
    assert command["command"] == "boost"
    assert command["boost"] == 1


async def test_discover() -> None:
    """Test device discovery."""
    with patch("socket.socket") as mock_sock:
        mock_sock.return_value.recvfrom.return_value = (
            json.dumps({"serial_number": "TEST123", "is_briiv_pro": 1}).encode(),
            ("192.168.1.100", 3334),
        )

        devices = await BriivAPI.discover(timeout=1)
        assert len(devices) == 1
        assert devices[0]["serial_number"] == "TEST123"
        assert devices[0]["host"] == "192.168.1.100"
        assert devices[0]["is_pro"] is True


async def test_callback_handling() -> None:
    """Test callback registration and handling."""
    api = BriivAPI(serial_number="TEST123")
    callback = AsyncMock()

    # Register callback
    api.register_callback(callback)
    assert len(api.callbacks) == 1

    # Test callback is called with data
    test_data = {"serial_number": "TEST123", "power": 1}
    await api._handle_device_data(
        json.dumps(test_data).encode(), test_data, ("192.168.1.100", 3334)
    )
    callback.assert_called_once_with(test_data)

    # Remove callback
    api.remove_callback(callback)
    assert len(api.callbacks) == 0


async def test_socket_error_handling(mock_socket) -> None:
    """Test error handling for socket operations."""
    mock_socket.return_value.bind.side_effect = OSError("Test error")

    with pytest.raises(BriivError):
        await BriivAPI.start_shared_listener(asyncio.get_event_loop())


async def test_cleanup() -> None:
    """Test cleanup of resources."""
    api = BriivAPI(serial_number="TEST123")

    with patch.object(api, "_shared_socket") as mock_socket:
        await api.stop_listening()
        mock_socket.close.assert_called_once()
        assert api._shared_socket is None
        assert not api._is_listening
