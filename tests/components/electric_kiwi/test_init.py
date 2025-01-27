"""Test the Electric Kiwi init."""

from homeassistant.core import HomeAssistant

from .conftest import ComponentSetup

from tests.common import MockConfigEntry


async def test_unique_id_migration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    component_setup: ComponentSetup,
) -> None:
    """Test that the unique ID is migrated to the customer number."""
    await component_setup()
    new_entry = hass.config_entries.async_get_entry(config_entry.entry_id)
    assert new_entry.minor_version == 2
    assert new_entry.unique_id == "123456"
