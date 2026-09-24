"""Tests for the Bitvis Power Hub integration."""

from bitvis_protobuf import powerhub_pb2
from bitvis_protobuf.parse import PayloadSample
import pytest

from homeassistant.components.bitvis.const import DATA_LISTENER_REGISTRY, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import find_listener_callback, setup_integration
from .conftest import TEST_DEVICE_MAC, FakeListener

from tests.common import MockConfigEntry


async def test_setup_entry(
    init_integration: MockConfigEntry,
) -> None:
    """Test successful integration setup."""
    assert init_integration.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that unloading stops the coordinator and unloads platforms."""
    assert DATA_LISTENER_REGISTRY in hass.data
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    assert init_integration.state is ConfigEntryState.NOT_LOADED
    assert DATA_LISTENER_REGISTRY not in hass.data


async def test_two_entries_share_listener(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_second_config_entry: MockConfigEntry,
    patch_shared_listener: FakeListener,
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
    patch_shared_listener.start.assert_awaited_once()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    patch_shared_listener.stop.assert_not_called()
    assert DATA_LISTENER_REGISTRY in hass.data

    assert await hass.config_entries.async_unload(mock_second_config_entry.entry_id)
    patch_shared_listener.stop.assert_awaited_once()
    assert DATA_LISTENER_REGISTRY not in hass.data


async def test_unload_after_dynamic_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_shared_listener: FakeListener,
) -> None:
    """Test unload succeeds after HAN sensors have been created dynamically."""
    await setup_integration(hass, mock_config_entry)

    payload = powerhub_pb2.Payload()
    payload.sample.power_active_delivered_to_client_kw = 2.0
    find_listener_callback(patch_shared_listener, TEST_DEVICE_MAC)(
        PayloadSample(mac_address=TEST_DEVICE_MAC, sample=payload.sample),
        ("192.168.1.100", 1234),
    )
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities_unavailable_before_data(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test diagnostic entities are unavailable after setup before any packet."""
    wifi_entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{TEST_DEVICE_MAC}_wifi_rssi",
    )
    assert wifi_entity_id is not None
    state = hass.states.get(wifi_entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
