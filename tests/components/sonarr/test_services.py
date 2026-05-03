"""Tests for Sonarr services."""

from unittest.mock import MagicMock

from aiopyarr import (
    ArrAuthenticationException,
    ArrConnectionException,
    Diskspace,
    SonarrQueue,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sonarr.const import (
    ATTR_DISKS,
    ATTR_ENTRY_ID,
    ATTR_EPISODES,
    ATTR_SHOWS,
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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "service",
    [
        SERVICE_GET_SERIES,
        SERVICE_GET_QUEUE,
        SERVICE_GET_DISKSPACE,
        SERVICE_GET_UPCOMING,
        SERVICE_GET_WANTED,
    ],
)
async def test_services_config_entry_not_loaded_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    service: str,
) -> None:
    """Test service call when config entry is in failed state."""
    # Create a second config entry that's not loaded
    unloaded_entry = MockConfigEntry(
        title="Sonarr",
        domain=DOMAIN,
        unique_id="unloaded",
    )
    unloaded_entry.add_to_hass(hass)

    assert unloaded_entry.state is ConfigEntryState.NOT_LOADED

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTRY_ID: unloaded_entry.entry_id},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_key == "not_loaded"


@pytest.mark.parametrize(
    "service",
    [
        SERVICE_GET_SERIES,
        SERVICE_GET_QUEUE,
        SERVICE_GET_DISKSPACE,
        SERVICE_GET_UPCOMING,
        SERVICE_GET_WANTED,
    ],
)
async def test_services_integration_not_found(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    service: str,
) -> None:
    """Test service call with non-existent config entry."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTRY_ID: "non_existent_entry_id"},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_key == "integration_not_found"


async def test_service_get_series(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test get_series service."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_SERIES,
        {ATTR_ENTRY_ID: init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    # Explicit assertion for specific behavior
    assert len(response[ATTR_SHOWS]) == 1

    # Snapshot for full structure validation
    assert response == snapshot


async def test_service_get_queue(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test get_queue service."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_QUEUE,
        {ATTR_ENTRY_ID: init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    # Explicit assertion for specific behavior
    assert len(response[ATTR_SHOWS]) == 1

    # Snapshot for full structure validation
    assert response == snapshot


@pytest.mark.parametrize(
    "service",
    [
        SERVICE_GET_SERIES,
        SERVICE_GET_QUEUE,
        SERVICE_GET_DISKSPACE,
        SERVICE_GET_UPCOMING,
        SERVICE_GET_WANTED,
    ],
)
async def test_services_entry_not_loaded(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    service: str,
) -> None:
    """Test services with unloaded config entry."""
    # Unload the entry
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTRY_ID: init_integration.entry_id},
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
        {ATTR_ENTRY_ID: init_integration.entry_id},
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
    snapshot: SnapshotAssertion,
) -> None:
    """Test get_diskspace service."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_DISKSPACE,
        {ATTR_ENTRY_ID: init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    # Explicit assertion for specific behavior
    assert len(response[ATTR_DISKS]) == 1

    # Snapshot for full structure validation
    assert response == snapshot


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
        {ATTR_ENTRY_ID: init_integration.entry_id},
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
    assert c_drive["free_space"] == 100000000000
    assert c_drive["total_space"] == 500000000000
    assert c_drive["unit"] == "bytes"

    # Check second disk (D:\Media)
    d_drive = disks["D:\\Media"]
    assert d_drive["path"] == "D:\\Media"
    assert d_drive["label"] == "Media Storage"
    assert d_drive["free_space"] == 2000000000000
    assert d_drive["total_space"] == 4000000000000

    # Check third disk (/mnt/nas)
    nas = disks["/mnt/nas"]
    assert nas["path"] == "/mnt/nas"
    assert nas["label"] == "NAS"
    assert nas["free_space"] == 10000000000000
    assert nas["total_space"] == 20000000000000


async def test_service_get_upcoming(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test get_upcoming service."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_UPCOMING,
        {ATTR_ENTRY_ID: init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    # Explicit assertion for specific behavior
    assert len(response[ATTR_EPISODES]) == 1

    # Snapshot for full structure validation
    assert response == snapshot


async def test_service_get_wanted(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test get_wanted service."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_WANTED,
        {ATTR_ENTRY_ID: init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    # Explicit assertion for specific behavior
    assert len(response[ATTR_EPISODES]) == 2

    # Snapshot for full structure validation
    assert response == snapshot


async def test_service_get_episodes(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test get_episodes service."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_EPISODES,
        {ATTR_ENTRY_ID: init_integration.entry_id, "series_id": 105},
        blocking=True,
        return_response=True,
    )

    # Explicit assertion for specific behavior
    assert len(response[ATTR_EPISODES]) == 3

    # Snapshot for full structure validation
    assert response == snapshot


async def test_service_get_episodes_with_season_filter(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test get_episodes service with season filter."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_EPISODES,
        {
            ATTR_ENTRY_ID: init_integration.entry_id,
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
        {ATTR_ENTRY_ID: init_integration.entry_id},
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


async def test_service_get_queue_season_pack(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sonarr_season_pack: MagicMock,
) -> None:
    """Test get_queue service with a season pack download."""
    # Set up integration with season pack queue data
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_QUEUE,
        {ATTR_ENTRY_ID: mock_config_entry.entry_id},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert ATTR_SHOWS in response
    shows = response[ATTR_SHOWS]

    # Should have only 1 entry (the season pack) instead of 3 (one per episode)
    assert len(shows) == 1

    # Check the season pack data structure
    season_pack = shows["House.S02.1080p.BluRay.x264-SHORTBREHD"]
    assert season_pack["title"] == "House"
    assert season_pack["season_number"] == 2
    assert season_pack["download_title"] == "House.S02.1080p.BluRay.x264-SHORTBREHD"

    # Check season pack specific fields
    assert season_pack["is_season_pack"] is True
    assert season_pack["episode_count"] == 3  # Episodes 1, 2, and 24 in fixture
    assert season_pack["episode_range"] == "E01-E24"
    assert season_pack["episode_identifier"] == "S02 (3 episodes)"

    # Check that basic download info is still present
    assert season_pack["size"] == 84429221268
    assert season_pack["status"] == "paused"
    assert season_pack["quality"] == "Bluray-1080p"


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_GET_SERIES, "async_get_series"),
        (SERVICE_GET_QUEUE, "async_get_queue"),
        (SERVICE_GET_DISKSPACE, "async_get_diskspace"),
        (SERVICE_GET_UPCOMING, "async_get_calendar"),
        (SERVICE_GET_WANTED, "async_get_wanted"),
    ],
)
async def test_services_api_connection_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_sonarr: MagicMock,
    service: str,
    method: str,
) -> None:
    """Test services with API connection error."""
    # Configure the mock to raise an exception
    getattr(mock_sonarr, method).side_effect = ArrConnectionException(
        "Connection failed"
    )

    with pytest.raises(HomeAssistantError, match="Failed to connect to Sonarr"):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTRY_ID: init_integration.entry_id},
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_GET_SERIES, "async_get_series"),
        (SERVICE_GET_QUEUE, "async_get_queue"),
        (SERVICE_GET_DISKSPACE, "async_get_diskspace"),
        (SERVICE_GET_UPCOMING, "async_get_calendar"),
        (SERVICE_GET_WANTED, "async_get_wanted"),
    ],
)
async def test_services_api_auth_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_sonarr: MagicMock,
    service: str,
    method: str,
) -> None:
    """Test services with API authentication error."""
    # Configure the mock to raise an exception
    getattr(mock_sonarr, method).side_effect = ArrAuthenticationException(
        "Authentication failed"
    )

    with pytest.raises(HomeAssistantError, match="Authentication failed for Sonarr"):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTRY_ID: init_integration.entry_id},
            blocking=True,
            return_response=True,
        )
