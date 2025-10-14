"""Test Control4 Media Player."""

import pytest

from homeassistant.core import HomeAssistant

from .conftest import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director", "mock_update_variables")
async def test_media_player_with_and_without_sources(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that rooms with sources create entities and rooms without are skipped."""
    # The default mock_c4_director fixture provides multi-room data:
    # Room 1 has video source, Room 2 has no sources (thermostat-only room)
    await setup_integration(hass, mock_config_entry)

    # Only 1 media_player entity should be created (Living Room with sources)
    states = hass.states.async_all("media_player")
    assert len(states) == 1
    assert states[0].name == "Living Room"
