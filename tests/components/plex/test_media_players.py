"""Tests for Plex media_players."""
from unittest.mock import patch

from plexapi.exceptions import NotFound
import requests_mock

from homeassistant.core import HomeAssistant


async def test_plex_tv_clients(
    hass: HomeAssistant,
    entry,
    setup_plex_server,
    requests_mock: requests_mock.Mocker,
    player_plexhtpc_resources,
) -> None:
    """Test getting Plex clients from plex.tv."""
    requests_mock.get("/resources", text=player_plexhtpc_resources)

    with patch("plexapi.myplex.MyPlexResource.connect", side_effect=NotFound):
        await setup_plex_server()
        await hass.async_block_till_done()

    media_players_before = len(hass.states.async_entity_ids("media_player"))
    await hass.config_entries.async_unload(entry.entry_id)

    # Ensure one more client is discovered
    await setup_plex_server()
    media_players_after = len(hass.states.async_entity_ids("media_player"))
    assert media_players_after == media_players_before + 1

    await hass.config_entries.async_remove(entry.entry_id)

    # Ensure only plex.tv resource client is found
    with patch("plexapi.server.PlexServer.sessions", return_value=[]):
        await setup_plex_server(disable_clients=True)

    assert len(hass.states.async_entity_ids("media_player")) == 1
