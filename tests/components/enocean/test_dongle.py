"""Tests for EnOcean dongle."""

from unittest.mock import Mock, patch

import pytest
import serial

from homeassistant.components.enocean import dongle


@pytest.mark.parametrize(
    "test_url",
    [
        "rfc2217://hostname:3333",
        "rfc2217://192.168.1.100:3333",
        "socket://localhost:5000",
        "socket://example.com:8080",
        "loop://",
        "spy://dev/ttyUSB0",
    ],
)
def test_validate_path_network_urls_valid(test_url: str) -> None:
    """Test validate_path with valid network URL formats."""
    with patch("serial.serial_for_url") as mock_serial:
        mock_conn = Mock()
        mock_serial.return_value = mock_conn
        result = dongle.validate_path(test_url)

    assert result is True
    mock_serial.assert_called_once_with(test_url, baudrate=57600, timeout=0.1)
    mock_conn.close.assert_called_once()


@pytest.mark.parametrize(
    "test_url",
    [
        "rfc2217://",  # Missing netloc
        "rfc2217:/hostname:3333",  # Missing second slash
        "rfc2217://hostname",  # Missing port
        "socket://",  # Missing netloc
        "socket://hostname",  # Missing port
        "http://example.com",  # Unsupported scheme
        "ftp://example.com",  # Unsupported scheme
    ],
)
def test_validate_path_network_urls_invalid_format(test_url: str) -> None:
    """Test validate_path with invalid network URL formats."""
    result = dongle.validate_path(test_url)
    assert result is False


def test_validate_path_network_url_connection_failure() -> None:
    """Test validate_path with network URL that fails to connect."""
    with patch("serial.serial_for_url") as mock_serial:
        mock_serial.side_effect = serial.SerialException("Connection refused")
        result = dongle.validate_path("rfc2217://unreachable:3333")

    assert result is False


def test_validate_path_backward_compatibility_local_path() -> None:
    """Test validate_path still works with local device paths."""
    with patch(
        "homeassistant.components.enocean.dongle.SerialCommunicator"
    ) as mock_comm:
        mock_comm.return_value = Mock()
        result = dongle.validate_path("/dev/ttyUSB0")

    assert result is True
    mock_comm.assert_called_once_with(port="/dev/ttyUSB0")


def test_validate_path_local_path_does_not_exist() -> None:
    """Test validate_path with non-existent local device path."""
    with patch(
        "homeassistant.components.enocean.dongle.SerialCommunicator"
    ) as mock_comm:
        mock_comm.side_effect = serial.SerialException("Device not found")
        result = dongle.validate_path("/dev/nonexistent")

    assert result is False


def test_is_serial_url() -> None:
    """Test _is_serial_url helper function."""
    assert dongle._is_serial_url("rfc2217://host:port") is True
    assert dongle._is_serial_url("socket://host:port") is True
    assert dongle._is_serial_url("loop://") is True
    assert dongle._is_serial_url("spy://dev/tty") is True
    assert dongle._is_serial_url("/dev/ttyUSB0") is False
    assert dongle._is_serial_url("/dev/serial/by-id/usb-EnOcean") is False
    assert dongle._is_serial_url("http://example.com") is False
