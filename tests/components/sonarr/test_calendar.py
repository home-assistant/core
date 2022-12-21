"""Test the Sonarr calendar entity."""
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.sonarr.calendar import get_sonarr_episode_events
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CALENDAR_ID = "calendar.sonarr_episodes"
DOMAIN = "sonarr"


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
    assert state
    assert state.name == "Sonarr Episodes"
    assert state.state == "off"


async def test_get_episodes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sonarr: MagicMock,
    entity_registry_enabled_by_default: AsyncMock,
) -> None:
    """Test data is extracted from the coordinator."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["upcoming"]
    episodes = await get_sonarr_episode_events(coordinator)
    assert len(episodes) == 1
