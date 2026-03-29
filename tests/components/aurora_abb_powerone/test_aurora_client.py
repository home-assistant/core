"""Tests for the aurora_abb_powerone AuroraClient abstraction."""

from unittest.mock import MagicMock, patch

from aurorapy.client import AuroraError, AuroraTimeoutError
import pytest
from serial import SerialException

from homeassistant.components.aurora_abb_powerone.aurora_client import (
    AuroraClient,
    AuroraClientError,
    AuroraClientTimeoutError,
    AuroraInverterData,
    AuroraInverterIdentifier,
)


@patch("homeassistant.components.aurora_abb_powerone.aurora_client.AuroraSerialClient")
def test_from_serial_creates_correct_client(mock_serial_class: MagicMock) -> None:
    """Test that from_serial creates an AuroraSerialClient with correct parameters."""
    AuroraClient.from_serial(inverter_serial_address=3, serial_comport="/dev/ttyUSB0")
    mock_serial_class.assert_called_once_with(
        address=3,
        port="/dev/ttyUSB0",
        parity="N",
        timeout=1,
    )


@patch("homeassistant.components.aurora_abb_powerone.aurora_client.AuroraTCPClient")
def test_from_tcp_creates_correct_client(mock_tcp_class: MagicMock) -> None:
    """Test that from_tcp creates an AuroraTCPClient with correct parameters."""
    AuroraClient.from_tcp(inverter_serial_address=3, tcp_host="127.0.0.1", tcp_port=502)
    mock_tcp_class.assert_called_once_with(
        ip="127.0.0.1",
        port=502,
        address=3,
        timeout=1,
    )


def test_try_connect_and_fetch_identifier_success() -> None:
    """Test successful identifier fetch."""
    mock_client = MagicMock()
    mock_client.serial_number.return_value = "9876543"
    mock_client.version.return_value = "9.8.7.6"
    mock_client.pn.return_value = "A.B.C"
    mock_client.firmware.return_value = "1.234"

    aurora = AuroraClient(mock_client)
    result = aurora.try_connect_and_fetch_identifier()

    assert isinstance(result, AuroraInverterIdentifier)
    assert result.serial_number == "9876543"
    assert result.model == "9.8.7.6 (A.B.C)"
    assert result.firmware == "1.234"
    mock_client.connect.assert_called_once()
    mock_client.close.assert_called_once()


def test_try_connect_and_fetch_identifier_aurora_error() -> None:
    """Test that AuroraError is wrapped in AuroraClientError."""
    mock_client = MagicMock()
    mock_client.connect.side_effect = AuroraError("Connection failed")

    aurora = AuroraClient(mock_client)
    with pytest.raises(AuroraClientError):
        aurora.try_connect_and_fetch_identifier()
    mock_client.close.assert_called_once()


def test_try_connect_and_fetch_identifier_close_suppressed_on_error() -> None:
    """Test that close() exceptions are suppressed after a connection failure."""
    mock_client = MagicMock()
    mock_client.connect.side_effect = AuroraError("failed")
    mock_client.close.side_effect = Exception("close failed")

    aurora = AuroraClient(mock_client)
    with pytest.raises(AuroraClientError):
        aurora.try_connect_and_fetch_identifier()
    # No exception from close() propagation


def test_try_connect_and_fetch_data_success() -> None:
    """Test successful data fetch with all measurements."""
    mock_client = MagicMock()
    mock_client.measure.side_effect = lambda idx, *_: {
        1: 235.9476,
        2: 2.7894,
        3: 45.678,
        4: 50.789,
        6: 1.2345,
        7: 2.3456,
        8: 12.345,
        9: 23.456,
        21: 9.876,
        23: 123.456,
        25: 0.9876,
        26: 234.567,
        27: 1.234,
        30: 0.1234,
    }[idx]
    mock_client.cumulated_energy.return_value = 12345.0
    mock_client.alarms.return_value = ["No alarm", "extra"]

    aurora = AuroraClient(mock_client)
    result = aurora.try_connect_and_fetch_data()

    assert isinstance(result, AuroraInverterData)
    assert result.grid_voltage == 235.9
    assert result.grid_current == 2.8
    assert result.instantaneouspower == 45.7
    assert result.grid_frequency == 50.8
    assert result.i_leak_dcdc == 1.2345
    assert result.i_leak_inverter == 2.3456
    assert result.power_in_1 == 12.3
    assert result.power_in_2 == 23.5
    assert result.temp == 9.9
    assert result.voltage_in_1 == 123.5
    assert result.current_in_1 == 1.0
    assert result.voltage_in_2 == 234.6
    assert result.current_in_2 == 1.2
    assert result.r_iso == 0.1234
    assert result.totalenergy == 12.35
    assert result.alarm == "No alarm"
    mock_client.connect.assert_called_once()
    mock_client.close.assert_called_once()


def test_try_connect_and_fetch_data_timeout() -> None:
    """Test that AuroraTimeoutError is wrapped in AuroraClientTimeoutError."""
    mock_client = MagicMock()
    mock_client.connect.return_value = None
    mock_client.measure.side_effect = AuroraTimeoutError("No response after 10s")

    aurora = AuroraClient(mock_client)
    with pytest.raises(AuroraClientTimeoutError):
        aurora.try_connect_and_fetch_data()
    mock_client.close.assert_called_once()


def test_try_connect_and_fetch_data_aurora_error() -> None:
    """Test that AuroraError is wrapped in AuroraClientError."""
    mock_client = MagicMock()
    mock_client.connect.return_value = None
    mock_client.measure.side_effect = AuroraError("some error")

    aurora = AuroraClient(mock_client)
    with pytest.raises(AuroraClientError):
        aurora.try_connect_and_fetch_data()
    mock_client.close.assert_called_once()


def test_try_connect_and_fetch_data_serial_exception() -> None:
    """Test that SerialException is wrapped in AuroraClientError."""
    mock_client = MagicMock()
    mock_client.connect.return_value = None
    mock_client.measure.side_effect = SerialException("serial error")

    aurora = AuroraClient(mock_client)
    with pytest.raises(AuroraClientError):
        aurora.try_connect_and_fetch_data()
    mock_client.close.assert_called_once()


def test_try_connect_and_fetch_data_close_suppressed() -> None:
    """Test that close() exceptions are suppressed after data fetch error."""
    mock_client = MagicMock()
    mock_client.connect.return_value = None
    mock_client.measure.side_effect = AuroraError("error")
    mock_client.close.side_effect = Exception("close failed")

    aurora = AuroraClient(mock_client)
    with pytest.raises(AuroraClientError):
        aurora.try_connect_and_fetch_data()
    # No exception from close() propagation
