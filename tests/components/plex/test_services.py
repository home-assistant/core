"""Tests for various Plex services."""
from unittest.mock import patch

from plexapi.exceptions import NotFound
import pytest

from homeassistant.components.media_player.const import MEDIA_TYPE_MUSIC
from homeassistant.components.plex.const import (
    CONF_SERVER,
    CONF_SERVER_IDENTIFIER,
    DOMAIN,
    PLEX_SERVER_CONFIG,
    SERVICE_REFRESH_LIBRARY,
    SERVICE_SCAN_CLIENTS,
)
from homeassistant.components.plex.services import play_on_sonos
from homeassistant.const import CONF_URL
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_OPTIONS, SECONDARY_DATA

from tests.common import MockConfigEntry


async def test_refresh_library(
    hass,
    mock_plex_server,
    setup_plex_server,
    requests_mock,
    empty_payload,
    plex_server_accounts,
    plex_server_base,
):
    """Test refresh_library service call."""
    url = mock_plex_server.url_in_use
    refresh = requests_mock.get(f"{url}/library/sections/1/refresh", status_code=200)

    # Test with non-existent server
    with pytest.raises(HomeAssistantError):
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_LIBRARY,
            {"server_name": "Not a Server", "library_name": "Movies"},
            True,
        )
    assert not refresh.called

    # Test with non-existent library
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_LIBRARY,
        {"library_name": "Not a Library"},
        True,
    )
    assert not refresh.called

    # Test with valid library
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_LIBRARY,
        {"library_name": "Movies"},
        True,
    )
    assert refresh.call_count == 1

    # Add a second configured server
    secondary_url = SECONDARY_DATA[PLEX_SERVER_CONFIG][CONF_URL]
    secondary_name = SECONDARY_DATA[CONF_SERVER]
    secondary_id = SECONDARY_DATA[CONF_SERVER_IDENTIFIER]
    requests_mock.get(
        secondary_url,
        text=plex_server_base.format(
            name=secondary_name, machine_identifier=secondary_id
        ),
    )
    requests_mock.get(f"{secondary_url}/accounts", text=plex_server_accounts)
    requests_mock.get(f"{secondary_url}/clients", text=empty_payload)
    requests_mock.get(f"{secondary_url}/status/sessions", text=empty_payload)

    entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data=SECONDARY_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=SECONDARY_DATA["server_id"],
    )

    await setup_plex_server(config_entry=entry_2)

    # Test multiple servers available but none specified
    with pytest.raises(HomeAssistantError) as excinfo:
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_LIBRARY,
            {"library_name": "Movies"},
            True,
        )
    assert "Multiple Plex servers configured" in str(excinfo.value)
    assert refresh.call_count == 1


async def test_scan_clients(hass, mock_plex_server):
    """Test scan_for_clients service call."""
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SCAN_CLIENTS,
        blocking=True,
    )


async def test_sonos_play_media(
    hass,
    entry,
    setup_plex_server,
    requests_mock,
    empty_payload,
    playqueue_1234,
    playqueue_created,
    plextv_account,
    sonos_resources,
):
    """Test playback from a Sonos media_player.play_media call."""
    media_content_id = (
        '{"library_name": "Music", "artist_name": "Artist", "album_name": "Album"}'
    )
    sonos_speaker_name = "Zone A"

    requests_mock.get("https://plex.tv/users/account", text=plextv_account)
    requests_mock.post("/playqueues", text=playqueue_created)
    playback_mock = requests_mock.get("/player/playback/playMedia", status_code=200)

    # Test with no Plex integration available
    with pytest.raises(HomeAssistantError) as excinfo:
        play_on_sonos(hass, MEDIA_TYPE_MUSIC, media_content_id, sonos_speaker_name)
    assert "Plex integration not configured" in str(excinfo.value)

    with patch(
        "homeassistant.components.plex.PlexServer.connect", side_effect=NotFound
    ):
        # Initialize Plex integration without setting up a server
        with pytest.raises(AssertionError):
            await setup_plex_server()

        # Test with no Plex servers available
        with pytest.raises(HomeAssistantError) as excinfo:
            play_on_sonos(hass, MEDIA_TYPE_MUSIC, media_content_id, sonos_speaker_name)
        assert "No Plex servers available" in str(excinfo.value)

    # Complete setup of a Plex server
    await hass.config_entries.async_unload(entry.entry_id)
    mock_plex_server = await setup_plex_server()

    # Test with no speakers available
    requests_mock.get("https://sonos.plex.tv/resources", text=empty_payload)
    with pytest.raises(HomeAssistantError) as excinfo:
        play_on_sonos(hass, MEDIA_TYPE_MUSIC, media_content_id, sonos_speaker_name)
    assert f"Sonos speaker '{sonos_speaker_name}' is not associated with" in str(
        excinfo.value
    )
    assert playback_mock.call_count == 0

    # Test with speakers available
    requests_mock.get("https://sonos.plex.tv/resources", text=sonos_resources)
    with patch.object(mock_plex_server.account, "_sonos_cache_timestamp", 0):
        play_on_sonos(hass, MEDIA_TYPE_MUSIC, media_content_id, sonos_speaker_name)
    assert playback_mock.call_count == 1

    # Test with speakers available and media key payload
    play_on_sonos(hass, MEDIA_TYPE_MUSIC, "100", sonos_speaker_name)
    assert playback_mock.call_count == 2

    # Test with speakers available and Plex server specified
    content_id_with_server = '{"plex_server": "Plex Server 1", "library_name": "Music", "artist_name": "Artist", "album_name": "Album"}'
    play_on_sonos(hass, MEDIA_TYPE_MUSIC, content_id_with_server, sonos_speaker_name)
    assert playback_mock.call_count == 3

    # Test with speakers available but media not found
    content_id_bad_media = '{"library_name": "Music", "artist_name": "Not an Artist"}'
    with pytest.raises(HomeAssistantError) as excinfo:
        play_on_sonos(hass, MEDIA_TYPE_MUSIC, content_id_bad_media, sonos_speaker_name)
    assert "Plex media not found" in str(excinfo.value)
    assert playback_mock.call_count == 3

    # Test with speakers available and playqueue
    requests_mock.get("https://1.2.3.4:32400/playQueues/1234", text=playqueue_1234)
    content_id_with_playqueue = '{"playqueue_id": 1234}'
    play_on_sonos(hass, MEDIA_TYPE_MUSIC, content_id_with_playqueue, sonos_speaker_name)
    assert playback_mock.call_count == 4

    # Test with speakers available and invalid playqueue
    requests_mock.get("https://1.2.3.4:32400/playQueues/1235", status_code=404)
    content_id_with_playqueue = '{"playqueue_id": 1235}'
    with pytest.raises(HomeAssistantError) as excinfo:
        play_on_sonos(
            hass, MEDIA_TYPE_MUSIC, content_id_with_playqueue, sonos_speaker_name
        )
    assert "PlayQueue '1235' could not be found" in str(excinfo.value)
    assert playback_mock.call_count == 4
