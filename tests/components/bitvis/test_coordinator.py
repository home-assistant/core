"""Tests for the Bitvis Power Hub coordinator."""

from unittest.mock import AsyncMock, MagicMock

from bitvis_protobuf import powerhub_pb2
from bitvis_protobuf.listener import FilterMac
from bitvis_protobuf.parse import PayloadDiagnostic, PayloadSample
import pytest

from homeassistant.components.bitvis.const import DEFAULT_PORT
from homeassistant.components.bitvis.coordinator import async_get_listener_registry
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import TEST_DEVICE_MAC, deliver_listener_payload

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("patch_shared_listener")


async def test_setup_registers_mac_filter_on_listener(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_shared_listener: MagicMock,
) -> None:
    """Test integration setup registers a MAC filter on the shared listener."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    patch_shared_listener.start.assert_awaited_once_with(DEFAULT_PORT)
    patch_shared_listener.register.assert_called_once()
    registered_filter = patch_shared_listener.register.call_args[0][0]
    assert isinstance(registered_filter, FilterMac)
    assert registered_filter.mac_address == TEST_DEVICE_MAC

    registry = async_get_listener_registry(hass)
    assert registry.get(DEFAULT_PORT) is patch_shared_listener


async def test_sample_payload_updates_coordinator_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_shared_listener: MagicMock,
) -> None:
    """Test that a sample payload updates coordinator data after setup."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    payload = powerhub_pb2.Payload()
    payload.sample.power_active_delivered_to_client_kw = 2.5
    parsed = PayloadSample(mac_address=TEST_DEVICE_MAC, sample=payload.sample)

    deliver_listener_payload(patch_shared_listener, TEST_DEVICE_MAC, parsed)
    await hass.async_block_till_done()

    assert coordinator.data.sample is parsed
    assert coordinator.last_update_success is True


async def test_diagnostic_payload_updates_coordinator_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_shared_listener: MagicMock,
) -> None:
    """Test that a diagnostic payload updates coordinator data after setup."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    payload = powerhub_pb2.Payload()
    payload.diagnostic.uptime_s = 999
    parsed = PayloadDiagnostic(
        mac_address=TEST_DEVICE_MAC, diagnostic=payload.diagnostic
    )

    deliver_listener_payload(patch_shared_listener, TEST_DEVICE_MAC, parsed)
    await hass.async_block_till_done()

    assert coordinator.data.diagnostic is parsed
    assert coordinator.data.boot_time is not None


async def test_diagnostic_payload_extracts_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_shared_listener: MagicMock,
) -> None:
    """Test that device_info fields are stored from a diagnostic payload."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    payload = powerhub_pb2.Payload()
    payload.diagnostic.uptime_s = 10
    payload.diagnostic.device_info.model_name = "PowerHub Gen2"
    payload.diagnostic.device_info.sw_version = "1.2.3"
    payload.diagnostic.device_info.mac_address = b"\xaa\xbb\xcc\xdd\xee\xff"

    deliver_listener_payload(
        patch_shared_listener,
        TEST_DEVICE_MAC,
        PayloadDiagnostic(mac_address=TEST_DEVICE_MAC, diagnostic=payload.diagnostic),
    )
    await hass.async_block_till_done()

    assert coordinator.data.model_name == "PowerHub Gen2"
    assert coordinator.data.sw_version == "1.2.3"
    assert coordinator.data.mac_address == TEST_DEVICE_MAC


async def test_diagnostic_payload_clears_device_info_when_absent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_shared_listener: MagicMock,
) -> None:
    """Test that device_info fields are cleared when absent in a later diagnostic."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    payload = powerhub_pb2.Payload()
    payload.diagnostic.uptime_s = 10
    payload.diagnostic.device_info.model_name = "PowerHub"
    payload.diagnostic.device_info.sw_version = "1.0"
    payload.diagnostic.device_info.mac_address = b"\xaa\xbb\xcc\xdd\xee\xff"
    deliver_listener_payload(
        patch_shared_listener,
        TEST_DEVICE_MAC,
        PayloadDiagnostic(mac_address=TEST_DEVICE_MAC, diagnostic=payload.diagnostic),
    )
    await hass.async_block_till_done()
    assert coordinator.data.model_name == "PowerHub"

    payload2 = powerhub_pb2.Payload()
    payload2.diagnostic.uptime_s = 20
    deliver_listener_payload(
        patch_shared_listener,
        TEST_DEVICE_MAC,
        PayloadDiagnostic(mac_address=TEST_DEVICE_MAC, diagnostic=payload2.diagnostic),
    )
    await hass.async_block_till_done()

    assert coordinator.data.mac_address == TEST_DEVICE_MAC
    assert coordinator.data.model_name is None
    assert coordinator.data.sw_version is None


async def test_two_entries_share_listener(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_second_config_entry: MockConfigEntry,
    patch_shared_listener: MagicMock,
) -> None:
    """Test that two entries on the same port share one library listener."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_second_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_second_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_second_config_entry.state is ConfigEntryState.LOADED
    patch_shared_listener.start.assert_awaited_once_with(DEFAULT_PORT)
    assert patch_shared_listener.register.call_count == 2

    registry = async_get_listener_registry(hass)
    assert registry.get(DEFAULT_PORT) is patch_shared_listener

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    patch_shared_listener.stop.assert_not_called()

    assert await hass.config_entries.async_unload(mock_second_config_entry.entry_id)
    patch_shared_listener.stop.assert_awaited_once()
    assert registry.get(DEFAULT_PORT) is None


async def test_setup_oserror_results_in_setup_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_shared_listener: MagicMock,
) -> None:
    """Test that OSError from SharedListener.start results in SETUP_RETRY."""
    mock_shared_listener.start = AsyncMock(side_effect=OSError("port in use"))
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_runtime_error_results_in_setup_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_shared_listener: MagicMock,
) -> None:
    """Test that RuntimeError from SharedListener.register results in SETUP_ERROR."""
    mock_shared_listener.register.side_effect = RuntimeError("duplicate filter")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
