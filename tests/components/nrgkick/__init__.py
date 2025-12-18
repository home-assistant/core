"""Tests for the NRGkick integration."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def async_setup_entry_with_return(
    hass: HomeAssistant, entry: MockConfigEntry
) -> bool:
    """Set up the component and return boolean success."""
    return await hass.config_entries.async_setup(entry.entry_id)


def create_mock_config_entry(
    domain="nrgkick",
    data=None,
    options=None,
    entry_id="test_entry",
    title="NRGkick",
    unique_id="TEST123456",
):
    """Create a mock config entry for testing."""
    return MockConfigEntry(
        domain=domain,
        data=data or {},
        options=options or {},
        entry_id=entry_id,
        title=title,
        unique_id=unique_id,
    )


__all__ = ["async_setup_entry_with_return", "create_mock_config_entry"]
