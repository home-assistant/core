"""Tests for the Bitvis Power Hub coordinator."""

from unittest.mock import AsyncMock, MagicMock, patch

from bitvis_protobuf import powerhub_pb2
from bitvis_protobuf.parse import PayloadDiagnostic, PayloadSample
import pytest

from homeassistant.components.bitvis.const import DOMAIN, MODEL_NAME
from homeassistant.components.bitvis.coordinator import (
    BitvisDataUpdateCoordinator,
    BitvisListenerRegistry,
    async_get_listener_registry,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.168.1.100", "port": 5000},
        unique_id="192.168.1.100:5000",
        title=MODEL_NAME,
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


async def test_coordinator_async_setup_registers_callback(
    hass: HomeAssistant, coordinator: BitvisDataUpdateCoordinator
) -> None:
    """Test that _async_setup registers callback with listener."""
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

    await coordinator.async_stop()


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
    assert coordinator.last_update_success is True
    ha_listener.assert_called()


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
    assert coordinator.data.boot_time is not None
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


# ---------------------------------------------------------------------------
# async_stop edge cases
# ---------------------------------------------------------------------------


async def test_coordinator_async_stop_without_listener(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that async_stop works when no listener is registered."""
    config_entry.add_to_hass(hass)
    coordinator = BitvisDataUpdateCoordinator(hass, config_entry, "192.168.1.100", 5000)

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
