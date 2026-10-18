"""Tests for the Broadlink integration setup."""

from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_device

from tests.common import MockConfigEntry


async def test_migrate_remove_clock_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the former time and select entities are removed on migration."""
    device = get_device("Guest room")
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)
    time_entry = entity_registry.async_get_or_create(
        Platform.TIME,
        DOMAIN,
        f"{device.mac}-device_time",
        config_entry=mock_entry,
    )
    select_entry = entity_registry.async_get_or_create(
        Platform.SELECT,
        DOMAIN,
        f"{device.mac}-dayofweek",
        config_entry=mock_entry,
    )

    await device.setup_entry(hass, mock_entry=mock_entry)

    assert mock_entry.state is ConfigEntryState.LOADED
    assert mock_entry.minor_version == 2
    assert entity_registry.async_get(time_entry.entity_id) is None
    assert entity_registry.async_get(select_entry.entity_id) is None


async def test_migrate_from_future_version(hass: HomeAssistant) -> None:
    """Test a config entry from a newer version is not migrated."""
    device = get_device("Guest room")
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=device.mac,
        title=device.name,
        data=device.get_entry_data(),
        version=2,
    )

    await device.setup_entry(hass, mock_entry=mock_entry)

    assert mock_entry.state is ConfigEntryState.MIGRATION_ERROR
