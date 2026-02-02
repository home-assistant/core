"""Test Lutron migration logic."""

from unittest.mock import MagicMock

from homeassistant.components.lutron.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_unique_id_migration(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test unique ID migration."""
    mock_config_entry.add_to_hass(hass)

    # Setup registries with legacy unique ID
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    legacy_unique_id = "12345678901_light_legacy_uuid"
    new_unique_id = "12345678901_light_uuid"

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, legacy_unique_id)},
        manufacturer="Lutron",
        name="Test Light",
    )

    entity = entity_registry.async_get_or_create(
        domain="light",
        platform="lutron",
        unique_id=legacy_unique_id,
        config_entry=mock_config_entry,
        device_id=device.id,
    )

    assert entity.unique_id == legacy_unique_id
    assert (DOMAIN, legacy_unique_id) in device.identifiers

    # Run setup
    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    # Check if unique ID migrated
    entity = entity_registry.async_get(entity.entity_id)
    assert entity.unique_id == new_unique_id

    device = device_registry.async_get(device.id)
    assert (DOMAIN, new_unique_id) in device.identifiers
    assert (DOMAIN, legacy_unique_id) not in device.identifiers
