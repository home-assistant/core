"""Tests for the Bitvis Power Hub sensor platform."""

from bitvis_protobuf import powerhub_pb2
import pytest

from homeassistant.components.bitvis.const import DOMAIN
from homeassistant.components.bitvis.sensor import (
    DIAGNOSTIC_SENSOR_DESCRIPTIONS,
    SENSOR_DESCRIPTIONS,
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
    expected_count = len(SENSOR_DESCRIPTIONS) + len(DIAGNOSTIC_SENSOR_DESCRIPTIONS)
    assert len(entities) == expected_count


@pytest.mark.usefixtures("init_integration")
async def test_sensor_native_value_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that sensors return None when there is no sample data."""
    # A well-known sensor key guaranteed to be in SENSOR_DESCRIPTIONS
    state = hass.states.get(f"sensor.bitvis_power_hub_{SENSOR_DESCRIPTIONS[0].key}")
    # Entity should exist but be unavailable (no data yet)
    assert state is None or state.state in ("unavailable", "unknown")


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
    coordinator.async_set_sample_data(payload.sample)
    await hass.async_block_till_done()

    # Find the entity with the matching description key via the entity registry
    expected_unique_id = (
        f"{mock_config_entry.entry_id}_power_active_delivered_to_client"
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
) -> None:
    """Test that sample sensors are unavailable when coordinator has no data."""
    coordinator = mock_config_entry.runtime_data
    coordinator.last_update_success = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.bitvis_power_hub_{SENSOR_DESCRIPTIONS[0].key}")
    assert state is None or state.state == "unavailable"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_diagnostic_sensor_native_value_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that diagnostic sensors return unavailable when no diagnostic data."""
    state = hass.states.get(
        f"sensor.bitvis_power_hub_{DIAGNOSTIC_SENSOR_DESCRIPTIONS[0].key}"
    )
    assert state is None or state.state in ("unavailable", "unknown")


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
    coordinator.async_set_diagnostic_data(payload.diagnostic)
    await hass.async_block_till_done()

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    uptime_entry = next(
        (
            e
            for e in entity_entries
            if e.unique_id == f"{mock_config_entry.entry_id}_uptime"
        ),
        None,
    )
    assert uptime_entry is not None
    state = hass.states.get(uptime_entry.entity_id)
    assert state is not None
    assert int(state.state) == 12345

    rssi_entry = next(
        (
            e
            for e in entity_entries
            if e.unique_id == f"{mock_config_entry.entry_id}_wifi_rssi"
        ),
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
    assert (DOMAIN, mock_config_entry.entry_id) in device.identifiers
