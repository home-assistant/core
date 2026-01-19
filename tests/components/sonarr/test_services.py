"""Tests for Sonarr services."""

from unittest.mock import MagicMock

from aiopyarr import SonarrQueue
import pytest

from homeassistant.components.sonarr.const import (
    ATTR_SHOWS,
    CONF_ENTRY_ID,
    DOMAIN,
    SERVICE_GET_QUEUE,
    SERVICE_GET_SERIES,
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
