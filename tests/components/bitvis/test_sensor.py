"""Tests for the Bitvis Power Hub sensor platform."""

from unittest.mock import AsyncMock, patch

from bitvis_protobuf import powerhub_pb2
from bitvis_protobuf.parse import PayloadDiagnostic, PayloadSample
import pytest

from homeassistant.components.bitvis.const import DOMAIN, MANUFACTURER, MODEL_NAME
from homeassistant.components.bitvis.sensor import (
    DIAGNOSTIC_SENSOR_DESCRIPTIONS,
    SENSOR_DESCRIPTIONS,
    UPTIME_DESCRIPTION,
    _build_device_info,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_sensor_platform_creates_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that all expected entities are registered."""
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    expected_count = len(SENSOR_DESCRIPTIONS) + len(DIAGNOSTIC_SENSOR_DESCRIPTIONS) + 1
    assert len(entities) == expected_count


@pytest.mark.usefixtures("init_integration")
async def test_sensor_native_value_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that sensors return unavailable/unknown when there is no sample data."""
    expected_unique_id = f"{mock_config_entry.unique_id}_{SENSOR_DESCRIPTIONS[0].key}"
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    matching = next(
        (entry for entry in entity_entries if entry.unique_id == expected_unique_id),
        None,
    )
    assert matching is not None
    state = hass.states.get(matching.entity_id)
    # Entity should exist but be unavailable/unknown (no data yet)
    assert state is not None
    assert state.state in ("unavailable", "unknown")


@pytest.mark.usefixtures("init_integration")
async def test_sensor_native_value_with_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that sensors return the correct value after receiving sample data."""
    coordinator = mock_config_entry.runtime_data

    payload = powerhub_pb2.Payload()
    payload.sample.power_active_delivered_to_client_kw = 3.5
    coordinator._handle_sample(PayloadSample(sample=payload.sample))
    await hass.async_block_till_done()

    # Find the entity with the matching description key via the entity registry
    expected_unique_id = (
        f"{mock_config_entry.unique_id}_power_active_delivered_to_client"
    )
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    matching = next(
        (e for e in entity_entries if e.unique_id == expected_unique_id), None
    )
    assert matching is not None
    state = hass.states.get(matching.entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(3.5)


@pytest.mark.usefixtures("init_integration")
async def test_sensor_unavailable_without_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that sample sensors are unavailable when coordinator has no data."""
    coordinator = mock_config_entry.runtime_data
    coordinator.last_update_success = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    # Resolve a known sensor entity via the entity registry using its unique_id
    base_unique_id = mock_config_entry.unique_id or mock_config_entry.entry_id
    expected_unique_id = f"{base_unique_id}_power_active_delivered_to_client"
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    matching = next(
        (entry for entry in entity_entries if entry.unique_id == expected_unique_id),
        None,
    )
    assert matching is not None
    state = hass.states.get(matching.entity_id)
    assert state is not None
    assert state.state == "unavailable"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_diagnostic_sensor_native_value_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that diagnostic sensors return unavailable when no diagnostic data."""
    base_unique_id = mock_config_entry.unique_id or mock_config_entry.entry_id
    expected_unique_id = f"{base_unique_id}_{UPTIME_DESCRIPTION.key}"
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    matching = next(
        (entry for entry in entity_entries if entry.unique_id == expected_unique_id),
        None,
    )
    assert matching is not None
    state = hass.states.get(matching.entity_id)
    assert state is not None
    assert state.state in ("unavailable", "unknown")


@pytest.mark.freeze_time("2026-01-01 12:00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_diagnostic_sensor_native_value_with_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that diagnostic sensors return correct values after receiving data."""
    coordinator = mock_config_entry.runtime_data

    payload = powerhub_pb2.Payload()
    payload.diagnostic.uptime_s = 12345
    payload.diagnostic.wifi_rssi_dbm = -65
    coordinator._handle_diagnostic(PayloadDiagnostic(diagnostic=payload.diagnostic))
    await hass.async_block_till_done()

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    base_unique_id = mock_config_entry.unique_id or mock_config_entry.entry_id
    uptime_entry = next(
        (e for e in entity_entries if e.unique_id == f"{base_unique_id}_uptime"),
        None,
    )
    assert uptime_entry is not None
    state = hass.states.get(uptime_entry.entity_id)
    assert state is not None
    # uptime_s=12345 → start = 2026-01-01T12:00:00 - 12345s = 2026-01-01T08:34:15
    assert state.state == "2026-01-01T08:34:15+00:00"

    rssi_entry = next(
        (e for e in entity_entries if e.unique_id == f"{base_unique_id}_wifi_rssi"),
        None,
    )
    assert rssi_entry is not None
    state = hass.states.get(rssi_entry.entity_id)
    assert state is not None
    assert int(state.state) == -65


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensor_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that entities report the correct device identifiers."""
    device_registry = dr.async_get(hass)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert entities

    device_id = entities[0].device_id
    device = device_registry.async_get(device_id)
    assert device is not None
    expected_identifier = (
        DOMAIN,
        mock_config_entry.unique_id or mock_config_entry.entry_id,
    )
    assert expected_identifier in device.identifiers


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensor_device_info_with_diagnostic_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that device_info property includes model, sw_version and MAC from diagnostics."""
    coordinator = mock_config_entry.runtime_data

    payload = powerhub_pb2.Payload()
    payload.diagnostic.uptime_s = 10
    payload.diagnostic.device_info.model_name = "PowerHub Gen2"
    payload.diagnostic.device_info.sw_version = "2.0.0"
    payload.diagnostic.device_info.mac_address = b"\xaa\xbb\xcc\xdd\xee\xff"
    coordinator._handle_diagnostic(PayloadDiagnostic(diagnostic=payload.diagnostic))
    await hass.async_block_till_done()

    # Verify the entity's device_info property returns the diagnostic values
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert entities
    entity = hass.data["entity_components"]["sensor"].get_entity(entities[0].entity_id)
    assert entity is not None
    info = entity.device_info
    assert info is not None
    assert info["model"] == "PowerHub Gen2"
    assert info["sw_version"] == "2.0.0"
    assert ("mac", "aa:bb:cc:dd:ee:ff") in info["connections"]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_diagnostic_sensor_unavailable_without_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that diagnostic sensors are unavailable when coordinator has no data."""
    coordinator = mock_config_entry.runtime_data
    coordinator.last_update_success = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    base_unique_id = mock_config_entry.unique_id or mock_config_entry.entry_id
    expected_unique_id = f"{base_unique_id}_uptime"
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    matching = next(
        (entry for entry in entity_entries if entry.unique_id == expected_unique_id),
        None,
    )
    assert matching is not None
    state = hass.states.get(matching.entity_id)
    assert state is not None
    assert state.state == "unavailable"


@pytest.mark.usefixtures("init_integration")
async def test_sensor_available_with_sample_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that sample sensors become available when sample data is present."""
    coordinator = mock_config_entry.runtime_data

    payload = powerhub_pb2.Payload()
    payload.sample.power_active_delivered_to_client_kw = 2.0
    coordinator._handle_sample(PayloadSample(sample=payload.sample))
    await hass.async_block_till_done()

    base_unique_id = mock_config_entry.unique_id or mock_config_entry.entry_id
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


@pytest.mark.freeze_time("2026-01-01 12:00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_diagnostic_sensor_available_with_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that diagnostic sensors become available with diagnostic data."""
    coordinator = mock_config_entry.runtime_data

    payload = powerhub_pb2.Payload()
    payload.diagnostic.uptime_s = 100
    coordinator._handle_diagnostic(PayloadDiagnostic(diagnostic=payload.diagnostic))
    await hass.async_block_till_done()

    base_unique_id = mock_config_entry.unique_id or mock_config_entry.entry_id
    expected_unique_id = f"{base_unique_id}_uptime"
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
    # uptime_s=100 → start = 2026-01-01T12:00:00 - 100s = 2026-01-01T11:58:20
    assert state.state == "2026-01-01T11:58:20+00:00"


# ---------------------------------------------------------------------------
# Direct unit tests for _build_device_info helper
# ---------------------------------------------------------------------------


async def test_build_device_info_no_diagnostic(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _build_device_info returns defaults when no diagnostic data."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.bitvis.coordinator.BitvisDataUpdateCoordinator._async_setup",
        new_callable=AsyncMock,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    info = _build_device_info(coordinator, "test-id")

    assert info["identifiers"] == {(DOMAIN, "test-id")}
    assert info["manufacturer"] == MANUFACTURER
    assert info["model"] == MODEL_NAME
    assert info.get("sw_version") is None


async def test_build_device_info_with_diagnostic(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _build_device_info includes model, sw_version and MAC from diagnostics."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.bitvis.coordinator.BitvisDataUpdateCoordinator._async_setup",
        new_callable=AsyncMock,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    payload = powerhub_pb2.Payload()
    payload.diagnostic.uptime_s = 10
    payload.diagnostic.device_info.model_name = "PowerHub Gen2"
    payload.diagnostic.device_info.sw_version = "2.0.0"
    payload.diagnostic.device_info.mac_address = b"\xaa\xbb\xcc\xdd\xee\xff"
    coordinator._handle_diagnostic(PayloadDiagnostic(diagnostic=payload.diagnostic))

    info = _build_device_info(coordinator, "test-id")

    assert info["model"] == "PowerHub Gen2"
    assert info["sw_version"] == "2.0.0"
    assert ("mac", "aa:bb:cc:dd:ee:ff") in info["connections"]
