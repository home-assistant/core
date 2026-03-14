"""Tests for the Bitvis Power Hub coordinator."""

import asyncio
from datetime import datetime, timedelta
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from bitvis_protobuf import powerhub_pb2
import pytest

from homeassistant.components.bitvis.const import DOMAIN, WATCHDOG_INTERVAL
from homeassistant.components.bitvis.coordinator import (
    BitvisDataUpdateCoordinator,
    BitvisUDPProtocol,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.1.100", "port": 5000},
        unique_id="192.168.1.100:5000",
        title="Bitvis Power Hub",
    )


@pytest.fixture
def coordinator(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> BitvisDataUpdateCoordinator:
    """Return a coordinator instance (not started)."""
    config_entry.add_to_hass(hass)
    return BitvisDataUpdateCoordinator(hass, config_entry, "192.168.1.100", 5000)


# ---------------------------------------------------------------------------
# BitvisUDPProtocol tests
# ---------------------------------------------------------------------------


def test_protocol_connection_made(coordinator: BitvisDataUpdateCoordinator) -> None:
    """Test connection_made stores the transport."""
    protocol = BitvisUDPProtocol(coordinator)
    transport = MagicMock(spec=asyncio.DatagramTransport)
    transport.get_extra_info.return_value = ("0.0.0.0", 5000)

    protocol.connection_made(transport)

    assert protocol.transport is transport


def test_protocol_datagram_received_sample(
    coordinator: BitvisDataUpdateCoordinator,
) -> None:
    """Test that a sample payload is dispatched to the coordinator."""
    protocol = BitvisUDPProtocol(coordinator)

    payload = powerhub_pb2.Payload()
    payload.sample.power_active_delivered_to_client_kw = 1.5
    data = payload.SerializeToString()

    with patch.object(coordinator, "async_set_sample_data") as mock_set:
        protocol.datagram_received(data, ("192.168.1.100", 1234))

    mock_set.assert_called_once()


def test_protocol_datagram_received_diagnostic(
    coordinator: BitvisDataUpdateCoordinator,
) -> None:
    """Test that a diagnostic payload is dispatched to the coordinator."""
    protocol = BitvisUDPProtocol(coordinator)

    payload = powerhub_pb2.Payload()
    payload.diagnostic.uptime_s = 42
    data = payload.SerializeToString()

    with patch.object(coordinator, "async_set_diagnostic_data") as mock_set:
        protocol.datagram_received(data, ("192.168.1.100", 1234))

    mock_set.assert_called_once()


def test_protocol_datagram_received_wrong_host(
    coordinator: BitvisDataUpdateCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that datagrams from unexpected hosts are ignored."""
    protocol = BitvisUDPProtocol(coordinator)

    payload = powerhub_pb2.Payload()
    payload.sample.power_active_delivered_to_client_kw = 1.5
    data = payload.SerializeToString()

    with (
        patch.object(coordinator, "async_set_sample_data") as mock_set,
        caplog.at_level(logging.DEBUG, logger="homeassistant.components.bitvis"),
    ):
        protocol.datagram_received(data, ("10.0.0.99", 1234))

    mock_set.assert_not_called()


def test_protocol_datagram_received_decode_error(
    coordinator: BitvisDataUpdateCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that malformed datagrams log an error and don't crash."""
    protocol = BitvisUDPProtocol(coordinator)

    with caplog.at_level(logging.ERROR, logger="homeassistant.components.bitvis"):
        protocol.datagram_received(b"not-valid-protobuf", ("192.168.1.100", 1234))

    assert "Failed to decode" in caplog.text


def test_protocol_error_received(
    coordinator: BitvisDataUpdateCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that UDP errors are logged."""
    protocol = BitvisUDPProtocol(coordinator)

    with caplog.at_level(logging.ERROR, logger="homeassistant.components.bitvis"):
        protocol.error_received(OSError("network error"))

    assert "UDP protocol error" in caplog.text


def test_protocol_connection_lost_with_exc(
    coordinator: BitvisDataUpdateCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test connection_lost with exception logs an error."""
    protocol = BitvisUDPProtocol(coordinator)

    with caplog.at_level(logging.ERROR, logger="homeassistant.components.bitvis"):
        protocol.connection_lost(OSError("closed"))

    assert "UDP connection lost" in caplog.text


def test_protocol_connection_lost_clean(
    coordinator: BitvisDataUpdateCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test connection_lost without exception logs a debug message."""
    protocol = BitvisUDPProtocol(coordinator)

    with caplog.at_level(logging.DEBUG, logger="homeassistant.components.bitvis"):
        protocol.connection_lost(None)

    assert "UDP connection closed" in caplog.text


# ---------------------------------------------------------------------------
# BitvisDataUpdateCoordinator tests
# ---------------------------------------------------------------------------


async def test_coordinator_async_start_stop(
    hass: HomeAssistant, coordinator: BitvisDataUpdateCoordinator
) -> None:
    """Test that async_start creates endpoint and watchdog task."""
    mock_transport = MagicMock(spec=asyncio.DatagramTransport)

    with (
        patch(
            "asyncio.get_event_loop",
            return_value=asyncio.get_event_loop(),
        ),
        patch.object(
            asyncio.get_event_loop(),
            "create_datagram_endpoint",
            new_callable=AsyncMock,
            return_value=(mock_transport, MagicMock()),
        ),
    ):
        await coordinator.async_start()

    assert coordinator._transport is mock_transport
    assert coordinator._watchdog_task is not None

    await coordinator.async_stop()

    assert coordinator._transport is None
    assert coordinator._watchdog_task is None


async def test_coordinator_async_start_oserror(
    hass: HomeAssistant, coordinator: BitvisDataUpdateCoordinator
) -> None:
    """Test that OSError from async_start propagates."""
    loop = asyncio.get_event_loop()

    with (
        patch.object(
            loop,
            "create_datagram_endpoint",
            new_callable=AsyncMock,
            side_effect=OSError("port in use"),
        ),
        patch("asyncio.get_event_loop", return_value=loop),
        pytest.raises(OSError),
    ):
        await coordinator.async_start()


async def test_coordinator_update_data_not_implemented(
    coordinator: BitvisDataUpdateCoordinator,
) -> None:
    """Test that _async_update_data raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        await coordinator._async_update_data()


async def test_coordinator_set_sample_data(
    hass: HomeAssistant, coordinator: BitvisDataUpdateCoordinator
) -> None:
    """Test that async_set_sample_data updates data and notifies."""
    sample = powerhub_pb2.Payload().sample
    sample.power_active_delivered_to_client_kw = 2.5

    listener = MagicMock()
    coordinator.async_add_listener(listener)

    coordinator.async_set_sample_data(sample)
    await hass.async_block_till_done()

    assert coordinator.data.sample is sample
    assert coordinator.data.timestamp is not None
    assert coordinator.last_update_success is True
    listener.assert_called()


async def test_coordinator_set_sample_data_recovery_log(
    hass: HomeAssistant,
    coordinator: BitvisDataUpdateCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a recovery log is emitted when data returns after unavailability."""
    coordinator._unavailable_logged = True
    sample = powerhub_pb2.Payload().sample

    with caplog.at_level(logging.INFO, logger="homeassistant.components.bitvis"):
        coordinator.async_set_sample_data(sample)

    assert "back online" in caplog.text
    assert coordinator._unavailable_logged is False


async def test_coordinator_set_diagnostic_data(
    hass: HomeAssistant, coordinator: BitvisDataUpdateCoordinator
) -> None:
    """Test that async_set_diagnostic_data updates data and notifies."""
    diag = powerhub_pb2.Payload().diagnostic
    diag.uptime_s = 999

    listener = MagicMock()
    coordinator.async_add_listener(listener)

    coordinator.async_set_diagnostic_data(diag)
    await hass.async_block_till_done()

    assert coordinator.data.diagnostic is diag
    assert coordinator.data.timestamp is not None
    assert coordinator.last_update_success is True
    listener.assert_called()


async def test_coordinator_set_diagnostic_data_with_device_info(
    hass: HomeAssistant, coordinator: BitvisDataUpdateCoordinator
) -> None:
    """Test that device_info fields are extracted from diagnostic payload."""
    payload = powerhub_pb2.Payload()
    payload.diagnostic.uptime_s = 10
    payload.diagnostic.device_info.model_name = "PowerHub Gen2"
    payload.diagnostic.device_info.sw_version = "1.2.3"
    payload.diagnostic.device_info.mac_address = b"\xaa\xbb\xcc\xdd\xee\xff"

    coordinator.async_set_diagnostic_data(payload.diagnostic)
    await hass.async_block_till_done()

    assert coordinator.data.model_name == "PowerHub Gen2"
    assert coordinator.data.sw_version == "1.2.3"
    assert coordinator.data.mac_address == "aa:bb:cc:dd:ee:ff"


async def test_coordinator_set_diagnostic_data_recovery_log(
    hass: HomeAssistant,
    coordinator: BitvisDataUpdateCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that recovery log is emitted for diagnostic path too."""
    coordinator._unavailable_logged = True
    diag = powerhub_pb2.Payload().diagnostic

    with caplog.at_level(logging.INFO, logger="homeassistant.components.bitvis"):
        coordinator.async_set_diagnostic_data(diag)

    assert "back online" in caplog.text
    assert coordinator._unavailable_logged is False


async def test_watchdog_no_data_does_nothing(
    hass: HomeAssistant,
    coordinator: BitvisDataUpdateCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that watchdog does nothing when no data has been received yet."""
    coordinator.last_update_success = True
    # timestamp is None — watchdog should not mark unavailable

    with (
        patch(
            "asyncio.sleep",
            new_callable=AsyncMock,
            side_effect=[None, asyncio.CancelledError()],
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._async_watchdog()

    assert coordinator.last_update_success is True
    assert "unavailable" not in caplog.text


async def test_watchdog_recent_data_does_nothing(
    hass: HomeAssistant,
    coordinator: BitvisDataUpdateCoordinator,
) -> None:
    """Test that watchdog does nothing when data is recent."""
    coordinator.data.timestamp = datetime.now()
    coordinator.last_update_success = True

    with (
        patch(
            "asyncio.sleep",
            new_callable=AsyncMock,
            side_effect=[None, asyncio.CancelledError()],
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._async_watchdog()

    assert coordinator.last_update_success is True


async def test_watchdog_stale_data_marks_unavailable(
    hass: HomeAssistant,
    coordinator: BitvisDataUpdateCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that watchdog marks coordinator unavailable on stale data."""
    coordinator.data.timestamp = (
        datetime.now() - WATCHDOG_INTERVAL - timedelta(seconds=1)
    )
    coordinator.last_update_success = True

    listener = MagicMock()
    coordinator.async_add_listener(listener)

    with (
        patch(
            "asyncio.sleep",
            new_callable=AsyncMock,
            side_effect=[None, asyncio.CancelledError()],
        ),
        caplog.at_level(logging.INFO, logger="homeassistant.components.bitvis"),
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._async_watchdog()

    assert coordinator.last_update_success is False
    assert coordinator._unavailable_logged is True
    assert "unavailable" in caplog.text
    listener.assert_called()


async def test_watchdog_unavailable_logs_only_once(
    hass: HomeAssistant,
    coordinator: BitvisDataUpdateCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that unavailability is logged only once, not on every watchdog tick."""
    coordinator.data.timestamp = (
        datetime.now() - WATCHDOG_INTERVAL - timedelta(seconds=1)
    )
    coordinator.last_update_success = False
    coordinator._unavailable_logged = True  # Already logged previously

    with (
        patch(
            "asyncio.sleep",
            new_callable=AsyncMock,
            side_effect=[None, asyncio.CancelledError()],
        ),
        caplog.at_level(logging.INFO, logger="homeassistant.components.bitvis"),
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._async_watchdog()

    assert caplog.text.count("unavailable") == 0
