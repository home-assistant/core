"""Tests for Plex media_players."""
from plexapi.exceptions import NotFound

from homeassistant.components.plex.const import DOMAIN, SERVERS

from .const import DEFAULT_DATA, DEFAULT_OPTIONS
from .mock_classes import MockPlexAccount, MockPlexServer

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_plex_tv_clients(hass):
    """Test getting Plex clients from plex.tv."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    mock_plex_server = MockPlexServer(config_entry=entry)
    mock_plex_account = MockPlexAccount()

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "homeassistant.components.plex.PlexWebsocket.listen"
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    server_id = mock_plex_server.machineIdentifier
    plex_server = hass.data[DOMAIN][SERVERS][server_id]

    resource = next(
        x
        for x in mock_plex_account.resources()
        if x.name.startswith("plex.tv Resource Player")
    )
    with patch(
        "plexapi.myplex.MyPlexAccount", return_value=mock_plex_account
    ), patch.object(resource, "connect", side_effect=NotFound):
        await plex_server._async_update_platforms()
        await hass.async_block_till_done()

    media_players_before = len(hass.states.async_entity_ids("media_player"))

    # Ensure one more client is discovered
    await hass.config_entries.async_unload(entry.entry_id)

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "homeassistant.components.plex.PlexWebsocket.listen"
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    plex_server = hass.data[DOMAIN][SERVERS][server_id]

    with patch("plexapi.myplex.MyPlexAccount", return_value=mock_plex_account):
        await plex_server._async_update_platforms()
        await hass.async_block_till_done()

    media_players_after = len(hass.states.async_entity_ids("media_player"))
    assert media_players_after == media_players_before + 1

    # Ensure only plex.tv resource client is found
    await hass.config_entries.async_unload(entry.entry_id)

    mock_plex_server.clear_clients()
    mock_plex_server.clear_sessions()

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "homeassistant.components.plex.PlexWebsocket.listen"
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    plex_server = hass.data[DOMAIN][SERVERS][server_id]

    with patch("plexapi.myplex.MyPlexAccount", return_value=mock_plex_account):
        await plex_server._async_update_platforms()
        await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("media_player")) == 1

    # Ensure cache gets called
    with patch("plexapi.myplex.MyPlexAccount", return_value=mock_plex_account):
        await plex_server._async_update_platforms()
        await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("media_player")) == 1
