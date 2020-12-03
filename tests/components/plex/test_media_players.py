"""Tests for Plex media_players."""
from plexapi.exceptions import NotFound

from homeassistant.components.plex.const import DOMAIN, SERVERS

from tests.async_mock import patch


async def test_plex_tv_clients(hass, entry, mock_plex_account, setup_plex_server):
    """Test getting Plex clients from plex.tv."""
    resource = next(
        x
        for x in mock_plex_account.resources()
        if x.name.startswith("plex.tv Resource Player")
    )
    with patch.object(resource, "connect", side_effect=NotFound):
        mock_plex_server = await setup_plex_server()
        await hass.async_block_till_done()

    server_id = mock_plex_server.machineIdentifier
    plex_server = hass.data[DOMAIN][SERVERS][server_id]
    media_players_before = len(hass.states.async_entity_ids("media_player"))

    # Ensure one more client is discovered
    await hass.config_entries.async_unload(entry.entry_id)
    mock_plex_server = await setup_plex_server()
    plex_server = hass.data[DOMAIN][SERVERS][server_id]
    media_players_after = len(hass.states.async_entity_ids("media_player"))
    assert media_players_after == media_players_before + 1

    # Ensure only plex.tv resource client is found
    await hass.config_entries.async_unload(entry.entry_id)
    mock_plex_server = await setup_plex_server(num_users=0)
    plex_server = hass.data[DOMAIN][SERVERS][server_id]
    assert len(hass.states.async_entity_ids("media_player")) == 1

    # Ensure cache gets called
    await plex_server._async_update_platforms()
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("media_player")) == 1
