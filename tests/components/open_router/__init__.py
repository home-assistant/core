"""Tests for the OpenRouter integration."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def get_subentry_id(mock_config_entry: MockConfigEntry, subentry_type: str) -> str:
    """Get the subentry ID for a given index."""
    ids = [
        subentry_id
        for subentry_id, subentry in mock_config_entry.subentries.items()
        if subentry.subentry_type == subentry_type
    ]
    if not ids:
        raise ValueError(f"No subentry found for type {subentry_type}")
    return ids[0]
