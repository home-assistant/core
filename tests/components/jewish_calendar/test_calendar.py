"""Tests for the Jewish Calendar calendar platform."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_calendar_exists(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that the calendar exists."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    state = hass.states.get("calendar.jewish_calendar_user_events")
    assert state
