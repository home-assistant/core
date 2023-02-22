"""Tests for Plex sensors."""
from datetime import datetime, timedelta
from http import HTTPStatus
from unittest.mock import patch

import pytest
import requests.exceptions
import requests_mock

from homeassistant.components.plex.const import PLEX_UPDATE_LIBRARY_SIGNAL
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt

from .helpers import trigger_plex_update, wait_for_debouncer

from tests.common import async_fire_time_changed

LIBRARY_UPDATE_PAYLOAD = {"StatusNotification": [{"title": "Library scan complete"}]}

TIMESTAMP = datetime(2021, 9, 1)


class MockPlexMedia:
    """Minimal mock of base plexapi media object."""

    key = "key"
    addedAt = str(TIMESTAMP)
    listType = "video"
    year = 2021


class MockPlexClip(MockPlexMedia):
    """Minimal mock of plexapi clip object."""

    TAG = "Video"
    type = "clip"
    title = "Clip 1"


class MockPlexMovie(MockPlexMedia):
    """Minimal mock of plexapi movie object."""

    TAG = "Video"
    type = "movie"
    title = "Movie 1"


class MockPlexMusic(MockPlexMedia):
    """Minimal mock of plexapi album object."""

    TAG = "Directory"
    listType = "audio"
    type = "album"
    title = "Album"
    parentTitle = "Artist"


class MockPlexTVEpisode(MockPlexMedia):
    """Minimal mock of plexapi episode object."""

    TAG = "Video"
    type = "episode"
    title = "Episode 5"
    grandparentTitle = "TV Show"
    seasonEpisode = "s01e05"
    year = None
    parentYear = 2021


async def test_library_sensor_values(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    setup_plex_server,
    mock_websocket,
    requests_mock: requests_mock.Mocker,
    library_movies_size,
    library_music_size,
    library_tvshows_size,
    library_tvshows_size_episodes,
    library_tvshows_size_seasons,
) -> None:
    """Test the library sensors."""
    requests_mock.get(
        "/library/sections/1/all?includeCollections=0",
        text=library_movies_size,
    )

    requests_mock.get(
        "/library/sections/2/all?includeCollections=0&type=2",
        text=library_tvshows_size,
    )
    requests_mock.get(
        "/library/sections/2/all?includeCollections=0&type=3",
        text=library_tvshows_size_seasons,
    )
    requests_mock.get(
        "/library/sections/2/all?includeCollections=0&type=4",
        text=library_tvshows_size_episodes,
    )

    requests_mock.get(
        "/library/sections/3/all?includeCollections=0",
        text=library_music_size,
    )

    mock_plex_server = await setup_plex_server()
    await wait_for_debouncer(hass)

    activity_sensor = hass.states.get("sensor.plex_plex_server_1")
    assert activity_sensor.state == "1"

    # Ensure sensor is created as disabled
    assert hass.states.get("sensor.plex_server_1_library_tv_shows") is None

    # Enable sensor and validate values
    entity_registry = er.async_get(hass)
    entity_registry.async_update_entity(
        entity_id="sensor.plex_server_1_library_tv_shows", disabled_by=None
    )
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )

    media = [MockPlexTVEpisode()]
    with patch("plexapi.library.LibrarySection.recentlyAdded", return_value=media):
        await hass.async_block_till_done()

    library_tv_sensor = hass.states.get("sensor.plex_server_1_library_tv_shows")
    assert library_tv_sensor.state == "10"
    assert library_tv_sensor.attributes["seasons"] == 1
    assert library_tv_sensor.attributes["shows"] == 1
    assert (
        library_tv_sensor.attributes["last_added_item"]
        == "TV Show - S01E05 - Episode 5"
    )
    assert library_tv_sensor.attributes["last_added_timestamp"] == str(TIMESTAMP)

    # Handle `requests` exception
    requests_mock.get(
        "/library/sections/2/all?includeCollections=0&type=2",
        exc=requests.exceptions.ReadTimeout,
    )
    trigger_plex_update(
        mock_websocket, msgtype="status", payload=LIBRARY_UPDATE_PAYLOAD
    )
    await hass.async_block_till_done()

    library_tv_sensor = hass.states.get("sensor.plex_server_1_library_tv_shows")
    assert library_tv_sensor.state == STATE_UNAVAILABLE

    assert "Could not update library sensor" in caplog.text

    # Ensure sensor updates properly when it recovers
    requests_mock.get(
        "/library/sections/2/all?includeCollections=0&type=2",
        text=library_tvshows_size,
    )
    trigger_plex_update(
        mock_websocket, msgtype="status", payload=LIBRARY_UPDATE_PAYLOAD
    )
    with patch("plexapi.library.LibrarySection.recentlyAdded", return_value=media):
        await hass.async_block_till_done()

    library_tv_sensor = hass.states.get("sensor.plex_server_1_library_tv_shows")
    assert library_tv_sensor.state == "10"

    # Handle library deletion
    requests_mock.get(
        "/library/sections/2/all?includeCollections=0&type=2",
        status_code=HTTPStatus.NOT_FOUND,
    )
    trigger_plex_update(
        mock_websocket, msgtype="status", payload=LIBRARY_UPDATE_PAYLOAD
    )
    await hass.async_block_till_done()

    library_tv_sensor = hass.states.get("sensor.plex_server_1_library_tv_shows")
    assert library_tv_sensor.state == STATE_UNAVAILABLE

    # Test movie library sensor
    entity_registry.async_update_entity(
        entity_id="sensor.plex_server_1_library_tv_shows",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    entity_registry.async_update_entity(
        entity_id="sensor.plex_server_1_library_movies", disabled_by=None
    )
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )

    media = [MockPlexMovie()]
    with patch("plexapi.library.LibrarySection.recentlyAdded", return_value=media):
        await hass.async_block_till_done()

    library_movies_sensor = hass.states.get("sensor.plex_server_1_library_movies")
    assert library_movies_sensor.state == "1"
    assert library_movies_sensor.attributes["last_added_item"] == "Movie 1 (2021)"
    assert library_movies_sensor.attributes["last_added_timestamp"] == str(TIMESTAMP)

    # Test with clip
    media = [MockPlexClip()]
    with patch("plexapi.library.LibrarySection.recentlyAdded", return_value=media):
        async_dispatcher_send(
            hass, PLEX_UPDATE_LIBRARY_SIGNAL.format(mock_plex_server.machine_identifier)
        )
        async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=3))
        await hass.async_block_till_done()

    library_movies_sensor = hass.states.get("sensor.plex_server_1_library_movies")
    assert library_movies_sensor.attributes["last_added_item"] == "Clip 1"

    # Test music library sensor
    entity_registry.async_update_entity(
        entity_id="sensor.plex_server_1_library_movies",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    entity_registry.async_update_entity(
        entity_id="sensor.plex_server_1_library_music", disabled_by=None
    )
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )

    media = [MockPlexMusic()]
    with patch("plexapi.library.LibrarySection.recentlyAdded", return_value=media):
        await hass.async_block_till_done()

    library_music_sensor = hass.states.get("sensor.plex_server_1_library_music")
    assert library_music_sensor.state == "1"
    assert library_music_sensor.attributes["artists"] == 1
    assert library_music_sensor.attributes["albums"] == 1
    assert library_music_sensor.attributes["last_added_item"] == "Artist - Album (2021)"
    assert library_music_sensor.attributes["last_added_timestamp"] == str(TIMESTAMP)
