"""Tests for the Bitvis Power Hub coordinator."""

import asyncio
from datetime import timedelta
import logging
import socket
from unittest.mock import AsyncMock, MagicMock, patch

from bitvis_protobuf import powerhub_pb2
from bitvis_protobuf.parse import PayloadDiagnostic, PayloadSample
import pytest

from homeassistant.components.bitvis.const import DOMAIN, WATCHDOG_INTERVAL
from homeassistant.components.bitvis.coordinator import (
    BitvisDataUpdateCoordinator,
    BitvisListenerRegistry,
    async_get_listener_registry,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

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
# BitvisDataUpdateCoordinator._handle_payload tests
# ---------------------------------------------------------------------------


def test_handle_payload_sample(
    coordinator: BitvisDataUpdateCoordinator,
) -> None:
    """Test that a PayloadSample is dispatched to _handle_sample."""
    payload = powerhub_pb2.Payload()
    payload.sample.power_active_delivered_to_client_kw = 1.5
    parsed = PayloadSample(sample=payload.sample)

    with patch.object(coordinator, "_handle_sample") as mock_handle:
        coordinator._handle_payload(parsed, ("192.168.1.100", 1234))

    mock_handle.assert_called_once_with(parsed)


def test_handle_payload_diagnostic(
    coordinator: BitvisDataUpdateCoordinator,
) -> None:
    """Test that a PayloadDiagnostic is dispatched to _handle_diagnostic."""
    payload = powerhub_pb2.Payload()
    payload.diagnostic.uptime_s = 42
    parsed = PayloadDiagnostic(diagnostic=payload.diagnostic)

    with patch.object(coordinator, "_handle_diagnostic") as mock_handle:
        coordinator._handle_payload(parsed, ("192.168.1.100", 1234))

    mock_handle.assert_called_once_with(parsed)


# ---------------------------------------------------------------------------
# BitvisDataUpdateCoordinator._async_setup / async_stop tests
# ---------------------------------------------------------------------------


async def test_coordinator_async_setup_registers_callback_and_starts_watchdog(
    hass: HomeAssistant, coordinator: BitvisDataUpdateCoordinator
) -> None:
    """Test that _async_setup registers callback with listener and starts watchdog."""
    mock_listener = MagicMock()
    mock_listener.start = AsyncMock()
    mock_listener.stop = AsyncMock()
    mock_listener.is_empty = True

    with patch(
        "homeassistant.components.bitvis.coordinator.SharedListener",
        return_value=mock_listener,
    ):
        await coordinator._async_setup()

    mock_listener.register.assert_called_once()
    registered_callback = mock_listener.register.call_args[0][1]
    assert callable(registered_callback)
    assert coordinator._watchdog_task is not None

    await coordinator.async_stop()
    assert coordinator._watchdog_task is None


async def test_coordinator_async_setup_reuses_existing_listener(
    hass: HomeAssistant, coordinator: BitvisDataUpdateCoordinator
) -> None:
    """Test that a second coordinator on the same port reuses the shared listener."""
    config_entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.1.101", "port": 5000},
        unique_id="192.168.1.101:5000",
    )
    config_entry2.add_to_hass(hass)
    coordinator2 = BitvisDataUpdateCoordinator(
        hass, config_entry2, "192.168.1.101", 5000
    )

    mock_listener = MagicMock()
    mock_listener.start = AsyncMock()
    mock_listener.stop = AsyncMock()
    mock_listener.is_empty = False

    with patch(
        "homeassistant.components.bitvis.coordinator.SharedListener",
        return_value=mock_listener,
    ):
        await coordinator._async_setup()
        await coordinator2._async_setup()

    # SharedListener() should only be instantiated once
    mock_listener.start.assert_called_once()

    registry = async_get_listener_registry(hass)
    assert isinstance(registry, BitvisListenerRegistry)
    assert registry.get(5000) is not None

    # Stop first — listener stays (still registered by coordinator2)
    mock_listener.is_empty = False
    await coordinator.async_stop()
    mock_listener.stop.assert_not_called()

    # Stop second — listener torn down
    mock_listener.is_empty = True
    await coordinator2.async_stop()
    mock_listener.stop.assert_called_once()

    assert registry.get(5000) is None


async def test_coordinator_async_setup_oserror_raises_update_failed(
    hass: HomeAssistant, coordinator: BitvisDataUpdateCoordinator
) -> None:
    """Test that OSError from listener.start raises UpdateFailed."""
    mock_listener = MagicMock()
    mock_listener.start = AsyncMock(side_effect=OSError("port in use"))

    with (
        patch(
            "homeassistant.components.bitvis.coordinator.SharedListener",
            return_value=mock_listener,
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_setup()


async def test_coordinator_async_setup_runtime_error_raises_entry_error(
    hass: HomeAssistant, coordinator: BitvisDataUpdateCoordinator
) -> None:
    """Test that RuntimeError from listener.register raises ConfigEntryError."""
    mock_listener = MagicMock()
    mock_listener.start = AsyncMock()
    mock_listener.stop = AsyncMock()
    mock_listener.is_empty = True
    mock_listener.register.side_effect = RuntimeError("duplicate IP")

    with (
        patch(
            "homeassistant.components.bitvis.coordinator.SharedListener",
            return_value=mock_listener,
        ),
        pytest.raises(ConfigEntryError),
    ):
        await coordinator._async_setup()


# ---------------------------------------------------------------------------
# _async_resolve_host tests
# ---------------------------------------------------------------------------


async def test_resolve_host_ipv6_literal(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test resolving an IPv6 host literal returns that address."""
    coordinator = BitvisDataUpdateCoordinator(hass, config_entry, "2001:db8::10", 5000)
    assert await coordinator._async_resolve_host() == {"2001:db8::10"}


async def test_resolve_host_raises_update_failed_on_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test unresolved non-IP host raises UpdateFailed."""
    coordinator = BitvisDataUpdateCoordinator(
        hass, config_entry, "powerhub.local", 5000
    )

    with (
        patch.object(
            asyncio.get_running_loop(), "getaddrinfo", side_effect=socket.gaierror
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_resolve_host()


async def test_resolve_host_ip_literal_with_dns(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test resolving an IP literal also present in DNS."""
    coordinator = BitvisDataUpdateCoordinator(hass, config_entry, "192.168.1.100", 5000)
    ips = await coordinator._async_resolve_host()
    assert "192.168.1.100" in ips


async def test_resolve_host_hostname_with_dns(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test resolving a hostname that DNS resolves to IP addresses."""
    coordinator = BitvisDataUpdateCoordinator(
        hass, config_entry, "powerhub.local", 5000
    )

    with patch.object(
        asyncio.get_running_loop(),
        "getaddrinfo",
        new_callable=AsyncMock,
        return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.168.1.50", 0)),
        ],
    ):
        ips = await coordinator._async_resolve_host()

    assert "192.168.1.50" in ips


# ---------------------------------------------------------------------------
# _async_update_data
# ---------------------------------------------------------------------------


async def test_coordinator_update_data_returns_data(
    coordinator: BitvisDataUpdateCoordinator,
) -> None:
    """Test that _async_update_data returns current data (push-based coordinator)."""
    result = await coordinator._async_update_data()
    assert result is coordinator.data


# ---------------------------------------------------------------------------
# _handle_sample tests
# ---------------------------------------------------------------------------


async def test_coordinator_handle_sample(
    hass: HomeAssistant, coordinator: BitvisDataUpdateCoordinator
) -> None:
    """Test that _handle_sample updates coordinator data and notifies listeners."""
    payload = powerhub_pb2.Payload()
    payload.sample.power_active_delivered_to_client_kw = 2.5
    parsed = PayloadSample(sample=payload.sample)

    ha_listener = MagicMock()
    coordinator.async_add_listener(ha_listener)

    coordinator._handle_sample(parsed)
    await hass.async_block_till_done()

    assert coordinator.data.sample is parsed
    assert coordinator.data.timestamp is not None
    assert coordinator.last_update_success is True
    ha_listener.assert_called()


async def test_coordinator_handle_sample_recovery_log(
    hass: HomeAssistant,
    coordinator: BitvisDataUpdateCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test recovery log is emitted when sample arrives after unavailability."""
    coordinator._unavailable_logged = True
    parsed = PayloadSample(sample=powerhub_pb2.Payload().sample)

    with caplog.at_level(logging.INFO, logger="homeassistant.components.bitvis"):
        coordinator._handle_sample(parsed)

    assert "back online" in caplog.text
    assert coordinator._unavailable_logged is False


# ---------------------------------------------------------------------------
# _handle_diagnostic tests
# ---------------------------------------------------------------------------


async def test_coordinator_handle_diagnostic(
    hass: HomeAssistant, coordinator: BitvisDataUpdateCoordinator
) -> None:
    """Test that _handle_diagnostic updates coordinator data and notifies listeners."""
    payload = powerhub_pb2.Payload()
    payload.diagnostic.uptime_s = 999
    parsed = PayloadDiagnostic(diagnostic=payload.diagnostic)

    ha_listener = MagicMock()
    coordinator.async_add_listener(ha_listener)

    coordinator._handle_diagnostic(parsed)
    await hass.async_block_till_done()

    assert coordinator.data.diagnostic is parsed
    assert coordinator.data.timestamp is not None
    assert coordinator.last_update_success is True
    ha_listener.assert_called()


async def test_coordinator_handle_diagnostic_with_device_info(
    hass: HomeAssistant, coordinator: BitvisDataUpdateCoordinator
) -> None:
    """Test that device_info fields are extracted and stored from diagnostic payload."""
    payload = powerhub_pb2.Payload()
    payload.diagnostic.uptime_s = 10
    payload.diagnostic.device_info.model_name = "PowerHub Gen2"
    payload.diagnostic.device_info.sw_version = "1.2.3"
    payload.diagnostic.device_info.mac_address = b"\xaa\xbb\xcc\xdd\xee\xff"

    coordinator._handle_diagnostic(PayloadDiagnostic(diagnostic=payload.diagnostic))
    await hass.async_block_till_done()

    assert coordinator.data.model_name == "PowerHub Gen2"
    assert coordinator.data.sw_version == "1.2.3"
    assert coordinator.data.mac_address == "aa:bb:cc:dd:ee:ff"


async def test_coordinator_handle_diagnostic_clears_device_info(
    hass: HomeAssistant, coordinator: BitvisDataUpdateCoordinator
) -> None:
    """Test that device_info fields are cleared when diagnostic has no device_info."""
    payload = powerhub_pb2.Payload()
    payload.diagnostic.uptime_s = 10
    payload.diagnostic.device_info.model_name = "PowerHub"
    payload.diagnostic.device_info.sw_version = "1.0"
    payload.diagnostic.device_info.mac_address = b"\xaa\xbb\xcc\xdd\xee\xff"
    coordinator._handle_diagnostic(PayloadDiagnostic(diagnostic=payload.diagnostic))
    assert coordinator.data.model_name == "PowerHub"

    payload2 = powerhub_pb2.Payload()
    payload2.diagnostic.uptime_s = 20
    coordinator._handle_diagnostic(PayloadDiagnostic(diagnostic=payload2.diagnostic))

    assert coordinator.data.mac_address is None
    assert coordinator.data.model_name is None
    assert coordinator.data.sw_version is None


async def test_coordinator_handle_diagnostic_recovery_log(
    hass: HomeAssistant,
    coordinator: BitvisDataUpdateCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test recovery log is emitted for the diagnostic path too."""
    coordinator._unavailable_logged = True
    parsed = PayloadDiagnostic(diagnostic=powerhub_pb2.Payload().diagnostic)

    with caplog.at_level(logging.INFO, logger="homeassistant.components.bitvis"):
        coordinator._handle_diagnostic(parsed)

    assert "back online" in caplog.text
    assert coordinator._unavailable_logged is False


# ---------------------------------------------------------------------------
# Watchdog tests
# ---------------------------------------------------------------------------


async def test_watchdog_no_data_does_nothing(
    hass: HomeAssistant,
    coordinator: BitvisDataUpdateCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that watchdog does nothing when no data has been received yet."""
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
    assert "unavailable" not in caplog.text


async def test_watchdog_recent_data_does_nothing(
    hass: HomeAssistant,
    coordinator: BitvisDataUpdateCoordinator,
) -> None:
    """Test that watchdog does nothing when data is recent."""
    coordinator.data.timestamp = dt_util.utcnow()
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
        dt_util.utcnow() - WATCHDOG_INTERVAL - timedelta(seconds=1)
    )
    coordinator.last_update_success = True

    ha_listener = MagicMock()
    coordinator.async_add_listener(ha_listener)

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
    ha_listener.assert_called()


async def test_watchdog_unavailable_logs_only_once(
    hass: HomeAssistant,
    coordinator: BitvisDataUpdateCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that unavailability is logged only once, not on every watchdog tick."""
    coordinator.data.timestamp = (
        dt_util.utcnow() - WATCHDOG_INTERVAL - timedelta(seconds=1)
    )
    coordinator.last_update_success = False
    coordinator._unavailable_logged = True

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


# ---------------------------------------------------------------------------
# async_stop edge cases
# ---------------------------------------------------------------------------


async def test_coordinator_async_stop_without_watchdog(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that async_stop works when no watchdog task is running."""
    config_entry.add_to_hass(hass)
    coordinator = BitvisDataUpdateCoordinator(hass, config_entry, "192.168.1.100", 5000)
    assert coordinator._watchdog_task is None

    await coordinator.async_stop()

    assert coordinator._registered_ips == set()


async def test_coordinator_async_stop_without_domain_data(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that async_stop works when hass.data has no domain data."""
    config_entry.add_to_hass(hass)
    coordinator = BitvisDataUpdateCoordinator(hass, config_entry, "192.168.1.100", 5000)
    hass.data.pop(DOMAIN, None)

    await coordinator.async_stop()

    assert coordinator._registered_ips == set()
