"""The tests for the opnsense device tracker platform."""

from unittest import mock

from homeassistant.components import device_tracker
from homeassistant.components.opnsense.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_device_tracker_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: mock.AsyncMock,
) -> None:
    """Test device tracker platform setup."""
    entity_registry = er.async_get(hass)

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

    # Check the MAC addresses are correct
    entity_unique_ids = {entity.unique_id for entity in device_tracker_entities}
    assert "ff:ff:ff:ff:ff:ff" in entity_unique_ids
    assert "ff:ff:ff:ff:ff:fe" in entity_unique_ids


async def test_device_tracker_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: mock.AsyncMock,
) -> None:
    """Test device tracker entity states and attributes."""
    entity_registry = er.async_get(hass)

    # Setup the integration
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Enable entities (device trackers are disabled by default)
    entity_registry.async_update_entity(
        "device_tracker.opnsense_device_ff_ff_ff_ff_ff_ff", disabled_by=None
    )
    entity_registry.async_update_entity("device_tracker.desktop", disabled_by=None)

    # Reload the config entry to activate the enabled entities
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Test first device (no hostname)
    entity_id_1 = "device_tracker.opnsense_device_ff_ff_ff_ff_ff_ff"
    state_1 = hass.states.get(entity_id_1)
    assert state_1 is not None
    assert state_1.state == "home"  # Should be connected since it's in ARP table
    assert state_1.attributes.get("ip") == "192.168.0.123"
    assert state_1.attributes.get("mac") == "ff:ff:ff:ff:ff:ff"
    assert state_1.attributes.get("interface") == "LAN"

    # Test second device (with hostname and manufacturer)
    entity_id_2 = "device_tracker.desktop"
    state_2 = hass.states.get(entity_id_2)
    assert state_2 is not None
    assert state_2.state == "home"  # Should be connected since it's in ARP table
    assert state_2.attributes.get("ip") == "192.168.0.167"
    assert state_2.attributes.get("mac") == "ff:ff:ff:ff:ff:fe"
    assert state_2.attributes.get("interface") == "LAN"
    assert state_2.attributes.get("manufacturer") == "OEM"


async def test_device_tracker_with_interfaces_filter(
    hass: HomeAssistant,
    mock_opnsense_client: mock.AsyncMock,
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
    mock_config_entry.runtime_data = {
        "opnsense_client": mock_opnsense_client.return_value,
        "tracker_interfaces": ["WAN"],
    }
    mock_config_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)

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
