"""Test the Sonarr calendar entity."""
from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CALENDAR_ID = "calendar.sonarr_episodes"


async def test_calendar(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sonarr: MagicMock,
    entity_registry_enabled_by_default: AsyncMock,
) -> None:
    """Test the creation and events in the calendar."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(CALENDAR_ID)
    assert state.name == "Sonarr Episodes"
    assert state.state == "off"
    assert state.attributes.get("message") == "Bob's Burgers"
    assert state.attributes.get("description") == "Easy Com-mercial, Easy Go-mercial"
    assert state.attributes.get("start_time") == "2014-01-26 17:30:00"
    assert state.attributes.get("end_time") == "2014-01-26 18:00:00"
