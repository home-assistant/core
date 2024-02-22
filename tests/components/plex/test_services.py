"""Tests for various Plex services."""
from http import HTTPStatus
from unittest.mock import patch

import plexapi.audio
from plexapi.exceptions import NotFound
import plexapi.playqueue
import pytest
import requests_mock

from homeassistant.components.media_player import MediaType
from homeassistant.components.plex.const import (
    CONF_SERVER,
    CONF_SERVER_IDENTIFIER,
    DOMAIN,
    PLEX_SERVER_CONFIG,
    PLEX_URI_SCHEME,
    SERVICE_REFRESH_LIBRARY,
    SERVICE_SCAN_CLIENTS,
)
from homeassistant.components.plex.services import process_plex_payload
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_DATA, DEFAULT_OPTIONS, SECONDARY_DATA

from tests.common import MockConfigEntry


async def test_refresh_library(
    hass: HomeAssistant,
    mock_plex_server,
    setup_plex_server,
    requests_mock: requests_mock.Mocker,
    empty_payload,
    plex_server_accounts,
    plex_server_base,
) -> None:
    """Test refresh_library service call."""
    url = mock_plex_server.url_in_use
    refresh = requests_mock.get(
        f"{url}/library/sections/1/refresh", status_code=HTTPStatus.OK
    )

    # Test with non-existent server
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_LIBRARY,
            {"server_name": "Not a Server", "library_name": "Movies"},
            True,
        )
    assert not refresh.called

    # Test with non-existent library
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_LIBRARY,
        {"library_name": "Not a Library"},
        True,
    )
    assert not refresh.called

    # Test with valid library
    await hass.services.async_call(
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
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_LIBRARY,
            {"library_name": "Movies"},
            True,
        )
    assert "Multiple Plex servers configured" in str(excinfo.value)
    assert refresh.call_count == 1


async def test_scan_clients(hass: HomeAssistant, mock_plex_server) -> None:
    """Test scan_for_clients service call."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SCAN_CLIENTS,
        blocking=True,
    )


async def test_lookup_media_for_other_integrations(
    hass: HomeAssistant,
    entry,
    setup_plex_server,
    requests_mock: requests_mock.Mocker,
    playqueue_1234,
    playqueue_created,
) -> None:
    """Test media lookup for media_player.play_media calls from cast/sonos."""
    CONTENT_ID = PLEX_URI_SCHEME + '{"library_name": "Music", "artist_name": "Artist"}'
    CONTENT_ID_KEY = PLEX_URI_SCHEME + "100"
    CONTENT_ID_BAD_MEDIA = (
        PLEX_URI_SCHEME + '{"library_name": "Music", "artist_name": "Not an Artist"}'
    )
    CONTENT_ID_PLAYQUEUE = PLEX_URI_SCHEME + '{"playqueue_id": 1234}'
    CONTENT_ID_BAD_PLAYQUEUE = PLEX_URI_SCHEME + '{"playqueue_id": 1235}'
    CONTENT_ID_SERVER = (
        PLEX_URI_SCHEME
        + '{"plex_server": "Plex Server 1", "library_name": "Music", "artist_name": "Artist"}'
    )
    CONTENT_ID_SHUFFLE = (
        PLEX_URI_SCHEME
        + '{"library_name": "Music", "artist_name": "Artist", "shuffle": 1}'
    )

    # Test with no Plex integration available
    with pytest.raises(HomeAssistantError) as excinfo:
        process_plex_payload(hass, MediaType.MUSIC, CONTENT_ID)
    assert "Plex integration not configured" in str(excinfo.value)

    with patch(
        "homeassistant.components.plex.PlexServer.connect", side_effect=NotFound
    ):
        # Initialize Plex integration without setting up a server
        with pytest.raises(AssertionError):
            await setup_plex_server()

        # Test with no Plex servers available
        with pytest.raises(HomeAssistantError) as excinfo:
            process_plex_payload(hass, MediaType.MUSIC, CONTENT_ID)
        assert "No Plex servers available" in str(excinfo.value)

    # Complete setup of a Plex server
    await hass.config_entries.async_unload(entry.entry_id)
    await setup_plex_server()

    # Test lookup success without playqueue
    result = process_plex_payload(
        hass, MediaType.MUSIC, CONTENT_ID, supports_playqueues=False
    )
    assert isinstance(result.media, plexapi.audio.Artist)
    assert not result.shuffle

    # Test media key payload without playqueue
    result = process_plex_payload(
        hass, MediaType.MUSIC, CONTENT_ID_KEY, supports_playqueues=False
    )
    assert isinstance(result.media, plexapi.audio.Track)
    assert not result.shuffle

    # Test with specified server without playqueue
    result = process_plex_payload(
        hass, MediaType.MUSIC, CONTENT_ID_SERVER, supports_playqueues=False
    )
    assert isinstance(result.media, plexapi.audio.Artist)
    assert not result.shuffle

    # Test shuffle without playqueue
    result = process_plex_payload(
        hass, MediaType.MUSIC, CONTENT_ID_SHUFFLE, supports_playqueues=False
    )
    assert isinstance(result.media, plexapi.audio.Artist)
    assert result.shuffle

    # Test with media not found
    with patch(
        "plexapi.library.LibrarySection.search",
        return_value=None,
        __qualname__="search",
    ):
        with pytest.raises(HomeAssistantError) as excinfo:
            process_plex_payload(hass, MediaType.MUSIC, CONTENT_ID_BAD_MEDIA)
        assert f"No {MediaType.MUSIC} results in 'Music' for" in str(excinfo.value)

    # Test with playqueue
    requests_mock.get("https://1.2.3.4:32400/playQueues/1234", text=playqueue_1234)
    result = process_plex_payload(hass, MediaType.MUSIC, CONTENT_ID_PLAYQUEUE)
    assert isinstance(result.media, plexapi.playqueue.PlayQueue)

    # Test with invalid playqueue
    requests_mock.get(
        "https://1.2.3.4:32400/playQueues/1235", status_code=HTTPStatus.NOT_FOUND
    )
    with pytest.raises(HomeAssistantError) as excinfo:
        process_plex_payload(hass, MediaType.MUSIC, CONTENT_ID_BAD_PLAYQUEUE)
    assert "PlayQueue '1235' could not be found" in str(excinfo.value)

    # Test playqueue is created with shuffle
    requests_mock.post("/playqueues", text=playqueue_created)
    result = process_plex_payload(hass, MediaType.MUSIC, CONTENT_ID_SHUFFLE)
    assert isinstance(result.media, plexapi.playqueue.PlayQueue)


async def test_lookup_media_with_urls(hass: HomeAssistant, mock_plex_server) -> None:
    """Test media lookup for media_player.play_media calls from cast/sonos."""
    CONTENT_ID_URL = f"{PLEX_URI_SCHEME}{DEFAULT_DATA[CONF_SERVER_IDENTIFIER]}/100"

    # Test URL format
    result = process_plex_payload(
        hass, MediaType.MUSIC, CONTENT_ID_URL, supports_playqueues=False
    )
    assert isinstance(result.media, plexapi.audio.Track)
    assert result.shuffle is False

    # Test URL format with shuffle
    CONTENT_ID_URL_WITH_SHUFFLE = CONTENT_ID_URL + "?shuffle=1"
    result = process_plex_payload(
        hass, MediaType.MUSIC, CONTENT_ID_URL_WITH_SHUFFLE, supports_playqueues=False
    )
    assert isinstance(result.media, plexapi.audio.Track)
    assert result.shuffle is True
    assert result.offset == 0
