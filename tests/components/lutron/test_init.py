"""Test Lutron integration setup."""

from unittest.mock import MagicMock

from homeassistant.components.lutron.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up the integration."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.client is mock_lutron
    assert len(mock_config_entry.runtime_data.lights) == 1

    # Verify that the unique ID is generated correctly.
    # This prevents regression in unique ID generation which would be a breaking change.
    entity_registry = er.async_get(hass)
    # The light from mock_lutron has uuid="light_uuid" and guid="12345678901"
    expected_unique_id = "12345678901_light_uuid"
    entry = entity_registry.async_get("light.test_light")
    assert entry.unique_id == expected_unique_id


async def test_unload_entry(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test unloading the integration."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_unique_id_migration(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test migration of legacy unique IDs to the newer UUID-based format.

    In older versions of the integration, unique IDs were based on a legacy UUID format.
    The integration now prefers a newer UUID format when available. This test ensures
    that existing entities and devices are automatically migrated to the new format
    without losing their registry entries.
    """
    mock_config_entry.add_to_hass(hass)

    # Setup registries with an entry using the "legacy" unique ID format.
    # This simulates a user who had configured the integration in an older version.
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    legacy_unique_id = "12345678901_light_legacy_uuid"
    new_unique_id = "12345678901_light_uuid"

    # Create a device in the registry using the legacy ID
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, legacy_unique_id)},
        manufacturer="Lutron",
        name="Test Light",
    )

    # Create an entity in the registry using the legacy ID
    entity = entity_registry.async_get_or_create(
        domain="light",
        platform="lutron",
        unique_id=legacy_unique_id,
        config_entry=mock_config_entry,
        device_id=device.id,
    )

    # Verify our starting state: registry holds the legacy ID
    assert entity.unique_id == legacy_unique_id
    assert (DOMAIN, legacy_unique_id) in device.identifiers

    # Trigger the integration setup.
    # The async_setup_entry logic will detect the legacy IDs in the registry
    # and update them to the new UUIDs provided by the mock_lutron fixture.
    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    # Verify that the entity's unique ID has been updated to the new format.
    entity = entity_registry.async_get(entity.entity_id)
    assert entity.unique_id == new_unique_id

    # Verify that the device's identifiers have also been migrated.
    device = device_registry.async_get(device.id)
    assert (DOMAIN, new_unique_id) in device.identifiers
    assert (DOMAIN, legacy_unique_id) not in device.identifiers
