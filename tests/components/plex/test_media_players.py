"""Tests for Plex media_players."""
from unittest.mock import patch

from plexapi.exceptions import NotFound

from .payloads import PLAYER_PLEXWEB_RESOURCES


async def test_plex_tv_clients(hass, entry, setup_plex_server, requests_mock):
    """Test getting Plex clients from plex.tv."""

    with patch("plexapi.myplex.MyPlexResource.connect", side_effect=NotFound):
        await setup_plex_server()
        await hass.async_block_till_done()

    media_players_before = len(hass.states.async_entity_ids("media_player"))

    # Ensure one more client is discovered
    requests_mock.get("/resources", text=PLAYER_PLEXWEB_RESOURCES)
    await hass.config_entries.async_unload(entry.entry_id)

    await setup_plex_server()

    media_players_after = len(hass.states.async_entity_ids("media_player"))
    assert media_players_after == media_players_before + 1

    # Ensure only plex.tv resource client is found
    await hass.config_entries.async_unload(entry.entry_id)

    with patch("plexapi.server.PlexServer.sessions", return_value=[]):
        await setup_plex_server(disable_clients=True)

    assert len(hass.states.async_entity_ids("media_player")) == 1
