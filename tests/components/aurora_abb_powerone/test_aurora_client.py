"""Test the aurorapy library integration."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from homeassistant.components.aurora_abb_powerone.aurora_client import (
    AuroraClient,
    AuroraClientError,
    AuroraClientTimeoutError,
    AuroraError,
    AuroraInverterData,
    AuroraInverterIdentifier,
    AuroraTimeoutError,
    SerialException,
)


def _make_base_client_mock() -> MagicMock:
    """Helper: create a mock with the attrs AuroraClient expects."""
    m = MagicMock()
    m.connect = MagicMock()
    m.close = MagicMock()
    m.serial_number = MagicMock()
    m.version = MagicMock()
    m.pn = MagicMock()
    m.firmware = MagicMock()
    m.measure = MagicMock()
    m.cumulated_energy = MagicMock()
    m.alarms = MagicMock()
    return m


def test_from_serial_builds_correct_aurorapy_client() -> None:
    """Test: from_serial() client builder."""
    with patch(
        "homeassistant.components.aurora_abb_powerone.aurora_client.AuroraSerialClient"
    ) as SerialCls:
        dummy = MagicMock()
        SerialCls.return_value = dummy

        client = AuroraClient.from_serial(
            inverter_serial_address=2, serial_comport="/dev/ttyUSB0"
        )

        SerialCls.assert_called_once_with(
            address=2, port="/dev/ttyUSB0", parity="N", timeout=1
        )
        assert client._client is dummy


def test_from_tcp_builds_correct_aurorapy_client() -> None:
    """Test: from_tcp() client builder."""
    with patch(
        "homeassistant.components.aurora_abb_powerone.aurora_client.AuroraTCPClient"
    ) as TCPCls:
        dummy = MagicMock()
        TCPCls.return_value = dummy

        client = AuroraClient.from_tcp(
            inverter_serial_address=2, tcp_host="127.0.0.1", tcp_port=502
        )

        TCPCls.assert_called_once_with(ip="127.0.0.1", port=502, address=2, timeout=1)
        assert client._client is dummy


def test_try_connect_and_fetch_identifier_success() -> None:
    """Test: successful inverter identifier retrieval."""
    base = _make_base_client_mock()
    base.serial_number.return_value = "SN123456"
    base.version.return_value = "Aurora V1.2"
    base.pn.return_value = "PVI-3.6-TL"
    base.firmware.return_value = "FW 5.17"

    client = AuroraClient(base)
    ident = client.try_connect_and_fetch_identifier()

    assert isinstance(ident, AuroraInverterIdentifier)
    assert ident.serial_number == "SN123456"
    assert ident.model == "Aurora V1.2 (PVI-3.6-TL)"
    assert ident.firmware == "FW 5.17"

    base.connect.assert_called_once()
    base.serial_number.assert_called_once()
    base.version.assert_called_once()
    base.pn.assert_called_once()
    base.firmware.assert_called_once_with(1)
    base.close.assert_called_once()


def test_try_connect_and_fetch_identifier_maps_aurora_error_and_closes() -> None:
    """Test: raised exceptions on identifier retrieval."""
    base = _make_base_client_mock()
    base.serial_number.side_effect = AuroraError("boom")

    client = AuroraClient(base)
    with pytest.raises(AuroraClientError):
        client.try_connect_and_fetch_identifier()

    base.connect.assert_called_once()
    base.close.assert_called_once()


def test_try_connect_and_fetch_identifier_suppresses_close_exception() -> None:
    """Test: close() method does not raise exception."""
    base = _make_base_client_mock()
    base.serial_number.return_value = "SN"
    base.version.return_value = "V"
    base.pn.return_value = "PN"
    base.firmware.return_value = "FW"
    base.close.side_effect = RuntimeError("cannot close")

    client = AuroraClient(base)
    # no exception should leak from close()
    ident = client.try_connect_and_fetch_identifier()
    assert ident.serial_number == "SN"


def test_try_connect_and_fetch_data_success_rounding_and_calls() -> None:
    """Test: data retrieval and number rounding."""
    base = _make_base_client_mock()

    measurements = {
        1: 230.16,  # grid_voltage -> 230.2
        2: 5.14,  # grid_current -> 5.1
        3: 1234.44,  # power -> 1234.4
        4: 49.94,  # freq -> 49.9
        6: 0.3,  # i_leak_dcdc (no rounding)
        7: 0.1,  # i_leak_inverter (no rounding)
        21: 45.25,  # temp -> 45.2
        30: 120000,  # r_iso (no rounding)
    }

    def measure_side_effect(idx, *args, **kwargs):
        return measurements[idx]

    base.measure.side_effect = measure_side_effect
    base.cumulated_energy.return_value = 123456  # Wh -> 123.46 kWh
    base.alarms.return_value = ["OK", "ignored"]

    client = AuroraClient(base)
    data = client.try_connect_and_fetch_data()

    assert isinstance(data, AuroraInverterData)
    assert data.grid_voltage == 230.2
    assert data.grid_current == 5.1
    assert data.instantaneouspower == 1234.4
    assert data.grid_frequency == 49.9
    assert data.i_leak_dcdc == 0.3
    assert data.i_leak_inverter == 0.1
    assert data.temp == 45.2
    assert data.r_iso == 120000
    assert data.totalenergy == 123.46
    assert data.alarm == "OK"

    expected = [
        call(1, True),
        call(2, True),
        call(3, True),
        call(4),
        call(6),
        call(7),
        call(21),
        call(30),
    ]

    assert base.measure.call_args_list == expected

    base.cumulated_energy.assert_called_once_with(5)
    base.alarms.assert_called_once()
    base.close.assert_called_once()


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (AuroraTimeoutError("t"), AuroraClientTimeoutError),
        (SerialException("s"), AuroraClientError),
        (AuroraError("a"), AuroraClientError),
    ],
)
def test_try_connect_and_fetch_data_error_mapping_and_close(exc, expected) -> None:
    """Test mapped exceptions."""
    base = _make_base_client_mock()
    # Raise at first measure call after connect
    base.measure.side_effect = exc

    client = AuroraClient(base)
    with pytest.raises(expected):
        client.try_connect_and_fetch_data()

    base.connect.assert_called_once()
    base.close.assert_called_once()


def test_try_connect_and_fetch_data_suppresses_close_exception_on_success() -> None:
    """Test: close() method does not raise exception."""
    base = _make_base_client_mock()
    base.measure.side_effect = lambda idx, *a, **k: {
        1: 1.0,
        2: 2.0,
        3: 3.0,
        4: 50.0,
        6: 0.0,
        7: 0.0,
        21: 25.0,
        30: 100000,
    }[idx]
    base.cumulated_energy.return_value = 1000
    base.alarms.return_value = ["OK"]
    base.close.side_effect = RuntimeError("cannot close")

    client = AuroraClient(base)
    data = client.try_connect_and_fetch_data()
    assert data.totalenergy == 1.0  # 1000 Wh -> 1.00 kWh


def test_try_connect_and_fetch_data_close_called_when_exception_on_close_is_suppressed() -> (
    None
):
    """Test raised exceptions."""
    base = _make_base_client_mock()
    base.measure.side_effect = AuroraError("read failed")
    base.close.side_effect = RuntimeError("cannot close")

    client = AuroraClient(base)
    with pytest.raises(AuroraClientError):
        client.try_connect_and_fetch_data()
    # even though close throws, it's suppressed and method raised mapped error only
