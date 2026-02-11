"""Tests for the Bitvis Power Hub sensor platform."""

from unittest.mock import MagicMock, patch

from bitvis_protobuf import powerhub_pb2
from bitvis_protobuf.parse import PayloadDiagnostic, PayloadSample
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import find_listener_callback, setup_integration
from .conftest import TEST_DEVICE_MAC

from tests.common import MockConfigEntry, snapshot_platform

DIAGNOSTIC_UNIQUE_IDS = {
    f"{TEST_DEVICE_MAC}_uptime",
    f"{TEST_DEVICE_MAC}_wifi_rssi",
    f"{TEST_DEVICE_MAC}_han_msg_successfully_parsed",
    f"{TEST_DEVICE_MAC}_han_msg_buffer_overflow",
}


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.fixture
def sample_payload() -> PayloadSample:
    """Return a sample payload with test data."""
    payload = powerhub_pb2.Payload()
    payload.sample.phase_voltage_l1_v = 230.0
    payload.sample.phase_voltage_l2_v = 229.5
    payload.sample.phase_voltage_l3_v = 231.2
    payload.sample.phase_current_l1_a = 10.5
    payload.sample.phase_current_l2_a = 8.3
    payload.sample.phase_current_l3_a = 12.1
    payload.sample.power_active_delivered_to_client_kw = 2.415
    payload.sample.power_active_delivered_by_client_kw = 0.0
    payload.sample.power_reactive_delivered_to_client_kvar = 0.5
    payload.sample.power_reactive_delivered_by_client_kvar = 0.0
    payload.sample.power_active_l1_delivered_to_client_kw = 0.8
    payload.sample.power_active_l2_delivered_to_client_kw = 0.7
    payload.sample.power_active_l3_delivered_to_client_kw = 0.915
    payload.sample.power_active_l1_delivered_by_client_kw = 0.0
    payload.sample.power_active_l2_delivered_by_client_kw = 0.0
    payload.sample.power_active_l3_delivered_by_client_kw = 0.0
    payload.sample.power_reactive_l1_delivered_to_client_kvar = 0.2
    payload.sample.power_reactive_l2_delivered_to_client_kvar = 0.15
    payload.sample.power_reactive_l3_delivered_to_client_kvar = 0.15
    payload.sample.power_reactive_l1_delivered_by_client_kvar = 0.0
    payload.sample.power_reactive_l2_delivered_by_client_kvar = 0.0
    payload.sample.power_reactive_l3_delivered_by_client_kvar = 0.0
    payload.sample.energy_active_delivered_to_client_kwh = 1234.56
    payload.sample.energy_active_delivered_by_client_kwh = 789.12
    payload.sample.energy_reactive_delivered_to_client_kvarh = 45.67
    payload.sample.energy_reactive_delivered_by_client_kvarh = 23.45
    payload.mac_address = b"\xaa\xbb\xcc\xdd\xee\xff"
    return PayloadSample(mac_address=TEST_DEVICE_MAC, sample=payload.sample)


@pytest.fixture
def diagnostic_payload() -> PayloadDiagnostic:
    """Return a diagnostic payload with test data."""
    payload = powerhub_pb2.Payload()
    payload.diagnostic.uptime_s = 86400
    payload.diagnostic.wifi_rssi_dbm = -65
    payload.diagnostic.device_info.model_name = "PowerHub Gen2"
    payload.diagnostic.device_info.sw_version = "2.0.0"
    payload.diagnostic.device_info.mac_address = b"\xaa\xbb\xcc\xdd\xee\xff"
    payload.diagnostic.han_msg_successfully_parsed = 1000
    payload.diagnostic.han_msg_buffer_overflow = 5
    payload.mac_address = b"\xaa\xbb\xcc\xdd\xee\xff"
    return PayloadDiagnostic(mac_address=TEST_DEVICE_MAC, diagnostic=payload.diagnostic)


@pytest.mark.freeze_time("2026-01-01 12:00:00")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    sample_payload: PayloadSample,
    diagnostic_payload: PayloadDiagnostic,
    patch_shared_listener: MagicMock,
) -> None:
    """Test all entities with snapshot."""
    with patch("homeassistant.components.bitvis._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    callback = find_listener_callback(patch_shared_listener, TEST_DEVICE_MAC)
    callback(sample_payload, ("192.168.1.100", 1234))
    callback(diagnostic_payload, ("192.168.1.100", 1234))
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_diagnostic_entities_created_at_setup(
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that diagnostic sensors are created at setup."""
    unique_ids = {
        entry.unique_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    assert unique_ids == DIAGNOSTIC_UNIQUE_IDS


@pytest.mark.usefixtures("init_integration")
async def test_entities_added_when_fields_become_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    patch_shared_listener: MagicMock,
) -> None:
    """Test that HAN sensors are created when their fields first appear."""
    base_unique_id = mock_config_entry.unique_id

    payload = powerhub_pb2.Payload()
    payload.sample.power_active_delivered_to_client_kw = 2.0
    find_listener_callback(patch_shared_listener, TEST_DEVICE_MAC)(
        PayloadSample(mac_address=TEST_DEVICE_MAC, sample=payload.sample),
        ("192.168.1.100", 1234),
    )
    await hass.async_block_till_done()

    unique_ids = {
        entry.unique_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    assert unique_ids == DIAGNOSTIC_UNIQUE_IDS | {
        f"{base_unique_id}_power_active_delivered_to_client"
    }

    payload.sample.phase_voltage_l1_v = 230.0
    find_listener_callback(patch_shared_listener, TEST_DEVICE_MAC)(
        PayloadSample(mac_address=TEST_DEVICE_MAC, sample=payload.sample),
        ("192.168.1.100", 1234),
    )
    await hass.async_block_till_done()

    unique_ids = {
        entry.unique_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    assert unique_ids == DIAGNOSTIC_UNIQUE_IDS | {
        f"{base_unique_id}_power_active_delivered_to_client",
        f"{base_unique_id}_phase_voltage_l1",
    }


@pytest.mark.usefixtures("init_integration")
async def test_sensors_become_available_with_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    patch_shared_listener: MagicMock,
) -> None:
    """Test that sensors become available when data arrives."""
    payload = powerhub_pb2.Payload()
    payload.sample.power_active_delivered_to_client_kw = 2.0
    payload.mac_address = b"\xaa\xbb\xcc\xdd\xee\xff"
    find_listener_callback(patch_shared_listener, TEST_DEVICE_MAC)(
        PayloadSample(mac_address=TEST_DEVICE_MAC, sample=payload.sample),
        ("192.168.1.100", 1234),
    )
    await hass.async_block_till_done()

    base_unique_id = mock_config_entry.unique_id
    expected_unique_id = f"{base_unique_id}_power_active_delivered_to_client"
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    matching = next(
        (e for e in entity_entries if e.unique_id == expected_unique_id), None
    )
    assert matching is not None
    state = hass.states.get(matching.entity_id)
    assert state is not None
    assert state.state != "unavailable"
    assert float(state.state) == pytest.approx(2.0)
