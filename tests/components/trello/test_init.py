"""Test the trello config flow."""

from homeassistant.core import HomeAssistant

from .conftest import ComponentSetup

from tests.common import MockConfigEntry


async def test_remove_entry(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
) -> None:
    """Test config entry is successfully removed."""
    await setup_integration()

    assert hass.config_entries.async_get_entry(config_entry.entry_id) is not None
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    assert hass.config_entries.async_get_entry(config_entry.entry_id) is None
