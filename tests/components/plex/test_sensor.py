"""Tests for Plex sensors."""

from datetime import datetime, timedelta
from http import HTTPStatus
from unittest.mock import patch

import pytest
import requests.exceptions
import requests_mock

from homeassistant.components.plex.const import (
    PLEX_UPDATE_LIBRARY_SIGNAL,
    PLEX_UPDATE_SENSOR_SIGNAL,
)
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .helpers import mock_source, trigger_plex_update, wait_for_debouncer

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
    entity_registry: er.EntityRegistry,
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

    activity_sensor = hass.states.get("sensor.plex_server_1")
    assert activity_sensor.state == "1"

    # Ensure sensor is created as disabled
    assert hass.states.get("sensor.plex_server_1_library_tv_shows") is None

    # Enable sensor and validate values
    entity_registry.async_update_entity(
        entity_id="sensor.plex_server_1_library_tv_shows", disabled_by=None
    )
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )

    media = [MockPlexTVEpisode()]
    with patch(
        "plexapi.library.LibrarySection.recentlyAdded",
        return_value=media,
        __qualname__="recentlyAdded",
    ):
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
    with patch(
        "plexapi.library.LibrarySection.recentlyAdded",
        return_value=media,
        __qualname__="recentlyAdded",
    ):
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
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )

    media = [MockPlexMovie()]
    with patch(
        "plexapi.library.LibrarySection.recentlyAdded",
        return_value=media,
        __qualname__="recentlyAdded",
    ):
        await hass.async_block_till_done()

    library_movies_sensor = hass.states.get("sensor.plex_server_1_library_movies")
    assert library_movies_sensor.state == "1"
    assert library_movies_sensor.attributes["last_added_item"] == "Movie 1 (2021)"
    assert library_movies_sensor.attributes["last_added_timestamp"] == str(TIMESTAMP)

    # Test with clip
    media = [MockPlexClip()]
    with patch(
        "plexapi.library.LibrarySection.recentlyAdded",
        return_value=media,
        __qualname__="recentlyAdded",
    ):
        async_dispatcher_send(
            hass, PLEX_UPDATE_LIBRARY_SIGNAL.format(mock_plex_server.machine_identifier)
        )
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
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
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )

    media = [MockPlexMusic()]
    with patch(
        "plexapi.library.LibrarySection.recentlyAdded",
        return_value=media,
        __qualname__="recentlyAdded",
    ):
        await hass.async_block_till_done()

    library_music_sensor = hass.states.get("sensor.plex_server_1_library_music")
    assert library_music_sensor.state == "1"
    assert library_music_sensor.attributes["artists"] == 1
    assert library_music_sensor.attributes["albums"] == 1
    assert library_music_sensor.attributes["last_added_item"] == "Artist - Album (2021)"
    assert library_music_sensor.attributes["last_added_timestamp"] == str(TIMESTAMP)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "session_fixture",
    [
        "session_photo",
        "session_transient",
        "session_live_tv",
    ],
)
async def test_plex_sensors_special_sessions(
    hass: HomeAssistant,
    setup_plex_server,
    requests_mock: requests_mock.Mocker,
    session_fixture: pytest.FixtureRequest,
    request: pytest.FixtureRequest,
) -> None:
    """Test the Plex sensors with various types of special sessions."""
    mock_plex_server = await setup_plex_server()
    await wait_for_debouncer(hass)

    # Use the parameterized session fixture
    session_xml = request.getfixturevalue(session_fixture)
    requests_mock.get("/status/sessions", text=session_xml)

    # Trigger an update
    async_dispatcher_send(
        hass,
        PLEX_UPDATE_SENSOR_SIGNAL.format(mock_plex_server.machine_identifier),
    )
    await hass.async_block_till_done()

    # Check that sensors are updated appropriately for each session type
    # You may need to adjust these assertions based on the expected behavior for each session type
    for sensor_name in (
        "year",
        "title",
        "filename",
        "codec",
        "codec_extended",
        "tmdb_id",
        "edition_title",
    ):
        sensor = hass.states.get(f"sensor.shield_android_tv_{sensor_name}")
        assert sensor
        assert sensor.state is not None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_plex_sensors_values(
    hass: HomeAssistant,
    setup_plex_server,
    requests_mock: requests_mock.Mocker,
    session_base,
) -> None:
    """Test the Plex sensors."""
    with patch("plexapi.video.MovieSession.source", new=mock_source):
        mock_plex_server = await setup_plex_server()
        await wait_for_debouncer(hass)

        # Use the session_base fixture
        requests_mock.get("/status/sessions", text=session_base)

        # Trigger an update
        async_dispatcher_send(
            hass,
            PLEX_UPDATE_SENSOR_SIGNAL.format(mock_plex_server.machine_identifier),
        )
        await hass.async_block_till_done()

        # Test year sensor
        year_sensor = hass.states.get("sensor.shield_android_tv_year")
        assert year_sensor
        assert year_sensor.state == "2000"

        # Test title sensor
        title_sensor = hass.states.get("sensor.shield_android_tv_title")
        assert title_sensor
        assert title_sensor.state == "Movie 1"

        # Test filename sensor
        filename_sensor = hass.states.get("sensor.shield_android_tv_filename")
        assert filename_sensor
        assert filename_sensor.state is not None

        # Test codec sensor
        codec_sensor = hass.states.get("sensor.shield_android_tv_codec")
        assert codec_sensor
        assert codec_sensor.state == "English (DTS 5.1)"

        # Test codec long sensor
        codec_extended = hass.states.get("sensor.shield_android_tv_codec_extended")
        assert codec_extended
        assert codec_extended.state == "DTS 5.1 @ 1536 kbps (English)"

        # Test edition title sensor
        edition_sensor = hass.states.get("sensor.shield_android_tv_edition_title")
        assert edition_sensor
        assert (
            edition_sensor.state == "Extended"
        )  # will extract from filename which is the most common situation

        # Test TMDB ID sensor
        tmdb_sensor = hass.states.get("sensor.shield_android_tv_tmdb_id")
        assert tmdb_sensor
        assert tmdb_sensor.state == "12345"

        # Test TVDB ID sensor
        tvdb_sensor = hass.states.get("sensor.shield_android_tv_tvdb_id")
        assert tvdb_sensor
        assert tvdb_sensor.state == "67890"
