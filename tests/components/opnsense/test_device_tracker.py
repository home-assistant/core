"""The tests for the opnsense device tracker platform."""

from datetime import timedelta
from unittest import mock

from aiopnsense import OPNsenseConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components import device_tracker
from homeassistant.components.opnsense import OPNsenseRuntimeData
from homeassistant.components.opnsense.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_opnsense_client")
async def test_device_tracker_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test device tracker platform setup."""

    # Setup the integration
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that device tracker entities are created
    device_tracker_entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    device_tracker_entities = [
        entity
        for entity in device_tracker_entities
        if entity.domain == device_tracker.DOMAIN
    ]

    # Should have 2 devices from ARP table
    assert len(device_tracker_entities) == 2

    # Check the unique IDs are correct
    entity_unique_ids = {entity.unique_id for entity in device_tracker_entities}
    assert "ff:ff:ff:ff:ff:ff" in entity_unique_ids
    assert "ff:ff:ff:ff:ff:fe" in entity_unique_ids


@pytest.mark.usefixtures("mock_opnsense_client")
async def test_device_tracker_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test device tracker entity states and attributes."""
    # Setup the integration
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_tracker_entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    device_tracker_entities = [
        entity
        for entity in device_tracker_entities
        if entity.domain == device_tracker.DOMAIN
    ]
    entity_ids_by_unique_id = {
        entity.unique_id: entity.entity_id for entity in device_tracker_entities
    }

    # Enable entities (device trackers are disabled by default)
    entity_registry.async_update_entity(
        entity_ids_by_unique_id["ff:ff:ff:ff:ff:ff"], disabled_by=None
    )
    entity_registry.async_update_entity(
        entity_ids_by_unique_id["ff:ff:ff:ff:ff:fe"], disabled_by=None
    )

    # Reload the config entry to activate the enabled entities
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Test first device (no hostname)
    entity_id_1 = entity_ids_by_unique_id["ff:ff:ff:ff:ff:ff"]
    state_1 = hass.states.get(entity_id_1)
    assert state_1 is not None
    assert state_1.state == "home"  # Should be connected since it's in ARP table
    assert state_1.attributes.get("ip") == "192.168.0.123"
    assert state_1.attributes.get("mac") == "ff:ff:ff:ff:ff:ff"

    # Test second device (with hostname and manufacturer)
    entity_id_2 = entity_ids_by_unique_id["ff:ff:ff:ff:ff:fe"]
    state_2 = hass.states.get(entity_id_2)
    assert state_2 is not None
    assert state_2.state == "home"  # Should be connected since it's in ARP table
    assert state_2.attributes.get("ip") == "192.168.0.167"
    assert state_2.attributes.get("mac") == "ff:ff:ff:ff:ff:fe"


async def test_device_tracker_with_interfaces_filter(
    hass: HomeAssistant,
    mock_opnsense_client: mock.AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test device tracker with interface filtering."""
    # Create config entry with interface filtering
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "url": "http://router.lan/api",
            "api_key": "key",
            "api_secret": "secret",
            "verify_ssl": False,
            "tracker_interfaces": ["WAN"],  # Filter to only WAN interface
        },
    )
    mock_config_entry.runtime_data = OPNsenseRuntimeData(
        client=mock_opnsense_client.return_value,
        tracker_interfaces=["WAN"],
    )
    mock_config_entry.add_to_hass(hass)

    # Setup the integration
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that no device tracker entities are created (since all devices are on LAN)
    device_tracker_entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    device_tracker_entities = [
        entity
        for entity in device_tracker_entities
        if entity.domain == device_tracker.DOMAIN
    ]

    assert len(device_tracker_entities) == 0


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_coordinator_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: mock.AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator wraps client errors as UpdateFailed."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.desktop").state != STATE_UNAVAILABLE

    mock_opnsense_client.get_arp_table.side_effect = OPNsenseConnectionError(
        "connection failed"
    )

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.desktop").state == STATE_UNAVAILABLE

    assert mock_opnsense_client.get_arp_table.call_count == 2
