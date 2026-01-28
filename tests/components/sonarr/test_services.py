"""Tests for Sonarr services."""

from unittest.mock import MagicMock

from aiopyarr import Diskspace, SonarrQueue
import pytest

from homeassistant.components.sonarr.const import (
    ATTR_DISKS,
    ATTR_EPISODES,
    ATTR_SHOWS,
    CONF_ENTRY_ID,
    DOMAIN,
    SERVICE_GET_DISKSPACE,
    SERVICE_GET_EPISODES,
    SERVICE_GET_QUEUE,
    SERVICE_GET_SERIES,
    SERVICE_GET_UPCOMING,
    SERVICE_GET_WANTED,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry


async def test_service_config_entry_not_loaded_state(
    hass: HomeAssistant,
    mock_sonarr: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test service call when config entry is in failed state."""
    mock_config_entry.add_to_hass(hass)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    with pytest.raises(ServiceValidationError, match="service_not_found"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_SERIES,
            {CONF_ENTRY_ID: mock_config_entry.entry_id},
            blocking=True,
            return_response=True,
        )


async def test_service_integration_not_found(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test service call with non-existent config entry."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_SERIES,
            {CONF_ENTRY_ID: "non_existent_entry_id"},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_key == "integration_not_found"


async def test_service_get_series(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test get_series service."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_SERIES,
        {CONF_ENTRY_ID: init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert ATTR_SHOWS in response
    shows = response[ATTR_SHOWS]
    assert isinstance(shows, dict)
    assert len(shows) == 1

    # Check the series data structure
    andy_griffith = shows["The Andy Griffith Show"]
    assert andy_griffith["id"] == 105
    assert andy_griffith["year"] == 1960
    assert andy_griffith["tvdb_id"] == 77754
    assert andy_griffith["imdb_id"] == "tt0053479"
    assert andy_griffith["status"] == "ended"
    assert andy_griffith["monitored"] is True

    # Check episode statistics
    assert andy_griffith["episode_file_count"] == 0
    assert andy_griffith["episode_count"] == 0
    assert andy_griffith["episodes_info"] == "0/0 Episodes"

    # Check images
    assert "images" in andy_griffith
    assert "fanart" in andy_griffith["images"]
    assert "banner" in andy_griffith["images"]
    assert "poster" in andy_griffith["images"]
    # Should use remoteUrl from fixture
    assert andy_griffith["images"]["fanart"].startswith("https://artworks.thetvdb.com")


async def test_service_get_queue(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test get_queue service."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_QUEUE,
        {CONF_ENTRY_ID: init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert ATTR_SHOWS in response
    shows = response[ATTR_SHOWS]
    assert isinstance(shows, dict)
    assert len(shows) == 1

    # Check the queue item data structure
    queue_item = shows["The.Andy.Griffith.Show.S01E01.x264-GROUP"]
    assert queue_item["id"] == 1503378561
    # Note: seriesId and episodeId may not be at top level in all API responses
    assert queue_item["series_id"] is None  # Not in fixture at top level
    assert queue_item["episode_id"] is None  # Not in fixture at top level
    assert queue_item["title"] == "The Andy Griffith Show"
    assert queue_item["download_title"] == "The.Andy.Griffith.Show.S01E01.x264-GROUP"
    assert queue_item["season_number"] is None  # Not in fixture at top level
    assert queue_item["episode_number"] == 1  # From episode object
    assert queue_item["episode_title"] == "The New Housekeeper"  # From episode object
    # Episode identifier requires season_number which is None
    assert "episode_identifier" not in queue_item
    assert queue_item["progress"] == "100.00%"
    assert queue_item["size"] == 4472186820
    assert queue_item["size_left"] == 0
    assert queue_item["status"] == "Downloading"
    assert "usenet" in queue_item["protocol"].lower()  # Protocol enum string
    assert queue_item["quality"] == "SD"

    # Check images from series
    assert "images" in queue_item
    assert len(queue_item["images"]) == 3
    assert "fanart" in queue_item["images"]
    assert "banner" in queue_item["images"]
    assert "poster" in queue_item["images"]


async def test_service_entry_not_loaded(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test services with unloaded config entry."""
    # Unload the entry
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_SERIES,
            {CONF_ENTRY_ID: init_integration.entry_id},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_key == "not_loaded"

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_QUEUE,
            {CONF_ENTRY_ID: init_integration.entry_id},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_key == "not_loaded"


async def test_service_get_queue_empty(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_sonarr: MagicMock,
) -> None:
    """Test get_queue service with empty queue."""
    # Mock empty queue response
    mock_sonarr.async_get_queue.return_value = SonarrQueue(
        {
            "page": 1,
            "pageSize": 10,
            "sortKey": "timeleft",
            "sortDirection": "ascending",
            "totalRecords": 0,
            "records": [],
        }
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_QUEUE,
        {CONF_ENTRY_ID: init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert ATTR_SHOWS in response
    shows = response[ATTR_SHOWS]
    assert isinstance(shows, dict)
    assert len(shows) == 0


async def test_service_get_diskspace(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test get_diskspace service."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_DISKSPACE,
        {CONF_ENTRY_ID: init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert ATTR_DISKS in response
    disks = response[ATTR_DISKS]
    assert isinstance(disks, dict)
    assert len(disks) == 1

    # Check the disk data structure (from diskspace.json fixture)
    disk = disks["C:\\"]
    assert disk["path"] == "C:\\"
    assert disk["label"] == ""
    assert disk["free_space_bytes"] == 282500067328
    assert disk["total_space_bytes"] == 499738734592
    # Check calculated values
    assert disk["free_space_gb"] == round(282500067328 / (1024**3), 2)
    assert disk["total_space_gb"] == round(499738734592 / (1024**3), 2)
    assert "used_space_gb" in disk
    assert "usage_percent" in disk


async def test_service_get_diskspace_multiple_drives(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_sonarr: MagicMock,
) -> None:
    """Test get_diskspace service with multiple drives."""
    # Mock multiple disks response
    mock_sonarr.async_get_diskspace.return_value = [
        Diskspace(
            {
                "path": "C:\\",
                "label": "System",
                "freeSpace": 100000000000,
                "totalSpace": 500000000000,
            }
        ),
        Diskspace(
            {
                "path": "D:\\Media",
                "label": "Media Storage",
                "freeSpace": 2000000000000,
                "totalSpace": 4000000000000,
            }
        ),
        Diskspace(
            {
                "path": "/mnt/nas",
                "label": "NAS",
                "freeSpace": 10000000000000,
                "totalSpace": 20000000000000,
            }
        ),
    ]

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_DISKSPACE,
        {CONF_ENTRY_ID: init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert ATTR_DISKS in response
    disks = response[ATTR_DISKS]
    assert isinstance(disks, dict)
    assert len(disks) == 3

    # Check first disk (C:\)
    c_drive = disks["C:\\"]
    assert c_drive["path"] == "C:\\"
    assert c_drive["label"] == "System"
    assert c_drive["free_space_bytes"] == 100000000000
    assert c_drive["total_space_bytes"] == 500000000000
    assert c_drive["free_space_gb"] == round(100000000000 / (1024**3), 2)
    assert c_drive["total_space_gb"] == round(500000000000 / (1024**3), 2)
    assert c_drive["usage_percent"] == 80.0  # 400GB used out of 500GB

    # Check second disk (D:\Media)
    d_drive = disks["D:\\Media"]
    assert d_drive["path"] == "D:\\Media"
    assert d_drive["label"] == "Media Storage"
    assert d_drive["free_space_bytes"] == 2000000000000
    assert d_drive["total_space_bytes"] == 4000000000000

    # Check third disk (/mnt/nas)
    nas = disks["/mnt/nas"]
    assert nas["path"] == "/mnt/nas"
    assert nas["label"] == "NAS"
    assert nas["free_space_bytes"] == 10000000000000
    assert nas["total_space_bytes"] == 20000000000000


async def test_service_get_upcoming(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test get_upcoming service."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_UPCOMING,
        {CONF_ENTRY_ID: init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert ATTR_EPISODES in response
    episodes = response[ATTR_EPISODES]
    assert isinstance(episodes, dict)
    assert len(episodes) == 1

    # Check the upcoming episode data structure (from calendar.json fixture)
    episode = episodes["Bob's Burgers S04E11"]
    assert episode["id"] == 14402
    assert episode["series_id"] == 3
    assert episode["season_number"] == 4
    assert episode["episode_number"] == 11
    assert episode["episode_identifier"] == "S04E11"
    assert episode["title"] == "Easy Com-mercial, Easy Go-mercial"
    assert "2014-01-26" in episode["air_date"]  # May include time component
    assert episode["has_file"] is False
    assert episode["monitored"] is True

    # Check series information
    assert episode["series_title"] == "Bob's Burgers"
    assert episode["series_year"] == 2011
    assert episode["series_tvdb_id"] == 194031
    assert episode["series_imdb_id"] == "tt1561755"
    assert episode["series_status"] == "continuing"
    assert episode["network"] == "FOX"

    # Check images
    assert "images" in episode
    assert "fanart" in episode["images"]
    assert "banner" in episode["images"]
    assert "poster" in episode["images"]


async def test_service_get_wanted(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test get_wanted service."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_WANTED,
        {CONF_ENTRY_ID: init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert ATTR_EPISODES in response
    episodes = response[ATTR_EPISODES]
    assert isinstance(episodes, dict)
    assert len(episodes) == 2

    # Check the wanted episode data structure (from wanted-missing.json fixture)
    # First episode - Bob's Burgers
    bobs_burgers = episodes["Bob's Burgers S04E11"]
    assert bobs_burgers["id"] == 14402
    assert bobs_burgers["series_id"] == 3
    assert bobs_burgers["season_number"] == 4
    assert bobs_burgers["episode_number"] == 11
    assert bobs_burgers["episode_identifier"] == "S04E11"
    assert bobs_burgers["title"] == "Easy Com-mercial, Easy Go-mercial"
    assert bobs_burgers["has_file"] is False
    assert bobs_burgers["monitored"] is True

    # Check series information
    assert bobs_burgers["series_title"] == "Bob's Burgers"
    assert bobs_burgers["series_year"] == 2011
    assert bobs_burgers["series_tvdb_id"] == 194031

    # Check images
    assert "images" in bobs_burgers
    assert "fanart" in bobs_burgers["images"]
    assert "banner" in bobs_burgers["images"]
    assert "poster" in bobs_burgers["images"]

    # Second episode - Andy Griffith Show
    andy_griffith = episodes["The Andy Griffith Show S01E01"]
    assert andy_griffith["id"] == 889
    assert andy_griffith["series_id"] == 17
    assert andy_griffith["season_number"] == 1
    assert andy_griffith["episode_number"] == 1
    assert andy_griffith["episode_identifier"] == "S01E01"
    assert andy_griffith["title"] == "The New Housekeeper"
    assert andy_griffith["series_title"] == "The Andy Griffith Show"
    assert andy_griffith["series_year"] == 1960
    assert andy_griffith["series_tvdb_id"] == 77754


async def test_service_get_episodes(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test get_episodes service."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_EPISODES,
        {CONF_ENTRY_ID: init_integration.entry_id, "series_id": 105},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert ATTR_EPISODES in response
    episodes = response[ATTR_EPISODES]
    assert isinstance(episodes, dict)
    assert len(episodes) == 3

    # Check the first episode
    ep1 = episodes["S01E01"]
    assert ep1["id"] == 1001
    assert ep1["series_id"] == 105
    assert ep1["tvdb_id"] == 123456
    assert ep1["season_number"] == 1
    assert ep1["episode_number"] == 1
    assert ep1["episode_identifier"] == "S01E01"
    assert ep1["title"] == "The New Housekeeper"
    assert "1960-10-03" in ep1["air_date"]
    assert ep1["has_file"] is False
    assert ep1["monitored"] is True
    assert ep1["runtime"] == 25
    assert "overview" in ep1

    # Check an episode with a file
    ep2 = episodes["S01E02"]
    assert ep2["id"] == 1002
    assert ep2["has_file"] is True
    assert ep2["episode_file_id"] == 5001

    # Check an episode with finale_type
    ep3 = episodes["S02E01"]
    assert ep3["id"] == 1003
    assert ep3["season_number"] == 2
    assert ep3["finale_type"] == "season"


async def test_service_get_episodes_with_season_filter(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test get_episodes service with season filter."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_EPISODES,
        {
            CONF_ENTRY_ID: init_integration.entry_id,
            "series_id": 105,
            "season_number": 1,
        },
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert ATTR_EPISODES in response
    episodes = response[ATTR_EPISODES]
    assert isinstance(episodes, dict)
    # Should only have season 1 episodes (2 of them)
    assert len(episodes) == 2
    assert "S01E01" in episodes
    assert "S01E02" in episodes
    assert "S02E01" not in episodes


async def test_service_get_queue_image_fallback(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_sonarr: MagicMock,
) -> None:
    """Test that get_queue uses url fallback when remoteUrl is not available."""
    # Mock queue response with images that only have 'url' (no 'remoteUrl')
    mock_sonarr.async_get_queue.return_value = SonarrQueue(
        {
            "page": 1,
            "pageSize": 10,
            "sortKey": "timeleft",
            "sortDirection": "ascending",
            "totalRecords": 1,
            "records": [
                {
                    "series": {
                        "title": "Test Series",
                        "sortTitle": "test series",
                        "seasonCount": 1,
                        "status": "continuing",
                        "overview": "A test series.",
                        "network": "Test Network",
                        "airTime": "20:00",
                        "images": [
                            {
                                "coverType": "fanart",
                                "url": "/MediaCover/1/fanart.jpg?lastWrite=123456",
                            },
                            {
                                "coverType": "poster",
                                "url": "/MediaCover/1/poster.jpg?lastWrite=123456",
                            },
                        ],
                        "seasons": [{"seasonNumber": 1, "monitored": True}],
                        "year": 2024,
                        "path": "/tv/Test Series",
                        "profileId": 1,
                        "seasonFolder": True,
                        "monitored": True,
                        "useSceneNumbering": False,
                        "runtime": 45,
                        "tvdbId": 12345,
                        "tvRageId": 0,
                        "tvMazeId": 0,
                        "firstAired": "2024-01-01T00:00:00Z",
                        "lastInfoSync": "2024-01-01T00:00:00Z",
                        "seriesType": "standard",
                        "cleanTitle": "testseries",
                        "imdbId": "tt1234567",
                        "titleSlug": "test-series",
                        "certification": "TV-14",
                        "genres": ["Drama"],
                        "tags": [],
                        "added": "2024-01-01T00:00:00Z",
                        "ratings": {"votes": 100, "value": 8.0},
                        "qualityProfileId": 1,
                        "id": 1,
                    },
                    "episode": {
                        "seriesId": 1,
                        "episodeFileId": 0,
                        "seasonNumber": 1,
                        "episodeNumber": 1,
                        "title": "Pilot",
                        "airDate": "2024-01-01",
                        "airDateUtc": "2024-01-01T00:00:00Z",
                        "overview": "The pilot episode.",
                        "hasFile": False,
                        "monitored": True,
                        "absoluteEpisodeNumber": 1,
                        "unverifiedSceneNumbering": False,
                        "id": 1,
                    },
                    "quality": {
                        "quality": {"id": 3, "name": "WEBDL-1080p"},
                        "revision": {"version": 1, "real": 0},
                    },
                    "size": 1000000000,
                    "title": "Test.Series.S01E01.1080p.WEB-DL",
                    "sizeleft": 500000000,
                    "timeleft": "00:10:00",
                    "estimatedCompletionTime": "2024-01-01T01:00:00Z",
                    "status": "Downloading",
                    "trackedDownloadStatus": "Ok",
                    "statusMessages": [],
                    "downloadId": "test123",
                    "protocol": "torrent",
                    "id": 1,
                }
            ],
        }
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_QUEUE,
        {CONF_ENTRY_ID: init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert ATTR_SHOWS in response
    shows = response[ATTR_SHOWS]
    assert len(shows) == 1

    queue_item = shows["Test.Series.S01E01.1080p.WEB-DL"]
    assert "images" in queue_item

    # Since remoteUrl is not available, the fallback should use base_url + url
    # The base_url from mock_config_entry is http://192.168.1.189:8989
    assert "fanart" in queue_item["images"]
    assert "poster" in queue_item["images"]
    # Check that the fallback constructed the URL with base_url prefix
    assert queue_item["images"]["fanart"] == (
        "http://192.168.1.189:8989/MediaCover/1/fanart.jpg?lastWrite=123456"
    )
    assert queue_item["images"]["poster"] == (
        "http://192.168.1.189:8989/MediaCover/1/poster.jpg?lastWrite=123456"
    )
