"""The tests for the Radarr platform."""
from unittest.mock import patch

import pytest

from homeassistant.const import DATA_GIGABYTES
from homeassistant.setup import async_setup_component


def mocked_exception(*args, **kwargs):
    """Mock exception thrown by requests.get."""
    raise OSError


def mocked_requests_get(*args, **kwargs):
    """Mock requests.get invocations."""

    class MockResponse:
        """Class to represent a mocked response."""

        def __init__(self, json_data, status_code):
            """Initialize the mock response class."""
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            """Return the json of the response."""
            return self.json_data

    url = str(args[0])
    if "api/calendar" in url:
        return MockResponse(
            [
                {
                    "title": "Resident Evil",
                    "sortTitle": "resident evil final chapter",
                    "sizeOnDisk": 0,
                    "status": "announced",
                    "overview": "Alice, Jill, Claire, Chris, Leon, Ada, and...",
                    "inCinemas": "2017-01-25T00:00:00Z",
                    "physicalRelease": "2017-01-27T00:00:00Z",
                    "images": [
                        {
                            "coverType": "poster",
                            "url": (
                                "/radarr/MediaCover/12/poster.jpg"
                                "?lastWrite=636208663600000000"
                            ),
                        },
                        {
                            "coverType": "banner",
                            "url": (
                                "/radarr/MediaCover/12/banner.jpg"
                                "?lastWrite=636208663600000000"
                            ),
                        },
                    ],
                    "website": "",
                    "downloaded": "false",
                    "year": 2017,
                    "hasFile": "false",
                    "youTubeTrailerId": "B5yxr7lmxhg",
                    "studio": "Impact Pictures",
                    "path": "/path/to/Resident Evil The Final Chapter (2017)",
                    "profileId": 3,
                    "monitored": "false",
                    "runtime": 106,
                    "lastInfoSync": "2017-01-24T14:52:40.315434Z",
                    "cleanTitle": "residentevilfinalchapter",
                    "imdbId": "tt2592614",
                    "tmdbId": 173897,
                    "titleSlug": "resident-evil-the-final-chapter-2017",
                    "genres": ["Action", "Horror", "Science Fiction"],
                    "tags": [],
                    "added": "2017-01-24T14:52:39.989964Z",
                    "ratings": {"votes": 363, "value": 4.3},
                    "alternativeTitles": ["Resident Evil: Rising"],
                    "qualityProfileId": 3,
                    "id": 12,
                }
            ],
            200,
        )
    if "api/command" in url:
        return MockResponse(
            [
                {
                    "name": "RescanMovie",
                    "startedOn": "0001-01-01T00:00:00Z",
                    "stateChangeTime": "2014-02-05T05:09:09.2366139Z",
                    "sendUpdatesToClient": "true",
                    "state": "pending",
                    "id": 24,
                }
            ],
            200,
        )
    if "api/movie" in url:
        return MockResponse(
            [
                {
                    "title": "Assassin's Creed",
                    "sortTitle": "assassins creed",
                    "sizeOnDisk": 0,
                    "status": "released",
                    "overview": "Lynch discovers he is a descendant of...",
                    "inCinemas": "2016-12-21T00:00:00Z",
                    "images": [
                        {
                            "coverType": "poster",
                            "url": (
                                "/radarr/MediaCover/1/poster.jpg"
                                "?lastWrite=636200219330000000"
                            ),
                        },
                        {
                            "coverType": "banner",
                            "url": (
                                "/radarr/MediaCover/1/banner.jpg"
                                "?lastWrite=636200219340000000"
                            ),
                        },
                    ],
                    "website": "https://www.ubisoft.com/en-US/",
                    "downloaded": "false",
                    "year": 2016,
                    "hasFile": "false",
                    "youTubeTrailerId": "pgALJgMjXN4",
                    "studio": "20th Century Fox",
                    "path": "/path/to/Assassin's Creed (2016)",
                    "profileId": 6,
                    "monitored": "true",
                    "runtime": 115,
                    "lastInfoSync": "2017-01-23T22:05:32.365337Z",
                    "cleanTitle": "assassinscreed",
                    "imdbId": "tt2094766",
                    "tmdbId": 121856,
                    "titleSlug": "assassins-creed-121856",
                    "genres": ["Action", "Adventure", "Fantasy", "Science Fiction"],
                    "tags": [],
                    "added": "2017-01-14T20:18:52.938244Z",
                    "ratings": {"votes": 711, "value": 5.2},
                    "alternativeTitles": ["Assassin's Creed: The IMAX Experience"],
                    "qualityProfileId": 6,
                    "id": 1,
                }
            ],
            200,
        )
    if "api/diskspace" in url:
        return MockResponse(
            [
                {
                    "path": "/data",
                    "label": "",
                    "freeSpace": 282500067328,
                    "totalSpace": 499738734592,
                }
            ],
            200,
        )
    if "api/system/status" in url:
        return MockResponse(
            {
                "version": "0.2.0.210",
                "buildTime": "2017-01-22T23:12:49Z",
                "isDebug": "false",
                "isProduction": "true",
                "isAdmin": "false",
                "isUserInteractive": "false",
                "startupPath": "/path/to/radarr",
                "appData": "/path/to/radarr/data",
                "osVersion": "4.8.13.1",
                "isMonoRuntime": "true",
                "isMono": "true",
                "isLinux": "true",
                "isOsx": "false",
                "isWindows": "false",
                "branch": "develop",
                "authentication": "forms",
                "sqliteVersion": "3.16.2",
                "urlBase": "",
                "runtimeVersion": (
                    "4.6.1 (Stable 4.6.1.3/abb06f1 Mon Oct  3 07:57:59 UTC 2016)"
                ),
            },
            200,
        )
    return MockResponse({"error": "Unauthorized"}, 401)


async def test_diskspace_no_paths(hass):
    """Test getting all disk space."""
    config = {
        "sensor": {
            "platform": "radarr",
            "api_key": "foo",
            "days": "2",
            "unit": DATA_GIGABYTES,
            "include_paths": [],
            "monitored_conditions": ["diskspace"],
        }
    }

    with patch(
        "requests.get",
        side_effect=mocked_requests_get,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

        entity = hass.states.get("sensor.radarr_disk_space")
        assert entity is not None
        assert "263.10" == entity.state
        assert "mdi:harddisk" == entity.attributes["icon"]
        assert DATA_GIGABYTES == entity.attributes["unit_of_measurement"]
        assert "Radarr Disk Space" == entity.attributes["friendly_name"]
        assert "263.10/465.42GB (56.53%)" == entity.attributes["/data"]


async def test_diskspace_paths(hass):
    """Test getting diskspace for included paths."""
    config = {
        "sensor": {
            "platform": "radarr",
            "api_key": "foo",
            "days": "2",
            "unit": DATA_GIGABYTES,
            "include_paths": ["/data"],
            "monitored_conditions": ["diskspace"],
        }
    }

    with patch(
        "requests.get",
        side_effect=mocked_requests_get,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

        entity = hass.states.get("sensor.radarr_disk_space")
        assert entity is not None
        assert "263.10" == entity.state
        assert "mdi:harddisk" == entity.attributes["icon"]
        assert DATA_GIGABYTES == entity.attributes["unit_of_measurement"]
        assert "Radarr Disk Space" == entity.attributes["friendly_name"]
        assert "263.10/465.42GB (56.53%)" == entity.attributes["/data"]


async def test_commands(hass):
    """Test getting running commands."""
    config = {
        "sensor": {
            "platform": "radarr",
            "api_key": "foo",
            "days": "2",
            "unit": DATA_GIGABYTES,
            "include_paths": ["/data"],
            "monitored_conditions": ["commands"],
        }
    }

    with patch(
        "requests.get",
        side_effect=mocked_requests_get,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

        entity = hass.states.get("sensor.radarr_commands")
        assert entity is not None
        assert 1 == int(entity.state)
        assert "mdi:code-braces" == entity.attributes["icon"]
        assert "Commands" == entity.attributes["unit_of_measurement"]
        assert "Radarr Commands" == entity.attributes["friendly_name"]
        assert "pending" == entity.attributes["RescanMovie"]


async def test_movies(hass):
    """Test getting the number of movies."""
    config = {
        "sensor": {
            "platform": "radarr",
            "api_key": "foo",
            "days": "2",
            "unit": DATA_GIGABYTES,
            "include_paths": ["/data"],
            "monitored_conditions": ["movies"],
        }
    }

    with patch(
        "requests.get",
        side_effect=mocked_requests_get,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

        entity = hass.states.get("sensor.radarr_movies")
        assert entity is not None
        assert 1 == int(entity.state)
        assert "mdi:television" == entity.attributes["icon"]
        assert "Movies" == entity.attributes["unit_of_measurement"]
        assert "Radarr Movies" == entity.attributes["friendly_name"]
        assert "false" == entity.attributes["Assassin's Creed (2016)"]


async def test_upcoming_multiple_days(hass):
    """Test the upcoming movies for multiple days."""
    config = {
        "sensor": {
            "platform": "radarr",
            "api_key": "foo",
            "days": "2",
            "unit": DATA_GIGABYTES,
            "include_paths": ["/data"],
            "monitored_conditions": ["upcoming"],
        }
    }

    with patch(
        "requests.get",
        side_effect=mocked_requests_get,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

        entity = hass.states.get("sensor.radarr_upcoming")
        assert entity is not None
        assert 1 == int(entity.state)
        assert "mdi:television" == entity.attributes["icon"]
        assert "Movies" == entity.attributes["unit_of_measurement"]
        assert "Radarr Upcoming" == entity.attributes["friendly_name"]
        assert "2017-01-27T00:00:00Z" == entity.attributes["Resident Evil (2017)"]


@pytest.mark.skip
async def test_upcoming_today(hass):
    """Test filtering for a single day.

    Radarr needs to respond with at least 2 days.
    """
    config = {
        "sensor": {
            "platform": "radarr",
            "api_key": "foo",
            "days": "1",
            "unit": DATA_GIGABYTES,
            "include_paths": ["/data"],
            "monitored_conditions": ["upcoming"],
        }
    }
    with patch(
        "requests.get",
        side_effect=mocked_requests_get,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()
        entity = hass.states.get("sensor.radarr_upcoming")
        assert 1 == int(entity.state)
        assert "mdi:television" == entity.attributes["icon"]
        assert "Movies" == entity.attributes["unit_of_measurement"]
        assert "Radarr Upcoming" == entity.attributes["friendly_name"]
        assert "2017-01-27T00:00:00Z" == entity.attributes["Resident Evil (2017)"]


async def test_system_status(hass):
    """Test the getting of the system status."""
    config = {
        "sensor": {
            "platform": "radarr",
            "api_key": "foo",
            "days": "2",
            "unit": DATA_GIGABYTES,
            "include_paths": ["/data"],
            "monitored_conditions": ["status"],
        }
    }
    with patch(
        "requests.get",
        side_effect=mocked_requests_get,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()
        entity = hass.states.get("sensor.radarr_status")
        assert entity is not None
        assert "0.2.0.210" == entity.state
        assert "mdi:information" == entity.attributes["icon"]
        assert "Radarr Status" == entity.attributes["friendly_name"]
        assert "4.8.13.1" == entity.attributes["osVersion"]


async def test_ssl(hass):
    """Test SSL being enabled."""
    config = {
        "sensor": {
            "platform": "radarr",
            "api_key": "foo",
            "days": "1",
            "unit": DATA_GIGABYTES,
            "include_paths": ["/data"],
            "monitored_conditions": ["upcoming"],
            "ssl": "true",
        }
    }
    with patch(
        "requests.get",
        side_effect=mocked_requests_get,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()
        entity = hass.states.get("sensor.radarr_upcoming")
        assert entity is not None
        assert 1 == int(entity.state)
        assert "mdi:television" == entity.attributes["icon"]
        assert "Movies" == entity.attributes["unit_of_measurement"]
        assert "Radarr Upcoming" == entity.attributes["friendly_name"]
        assert "2017-01-27T00:00:00Z" == entity.attributes["Resident Evil (2017)"]


async def test_exception_handling(hass):
    """Test exception being handled."""
    config = {
        "sensor": {
            "platform": "radarr",
            "api_key": "foo",
            "days": "1",
            "unit": DATA_GIGABYTES,
            "include_paths": ["/data"],
            "monitored_conditions": ["upcoming"],
        }
    }
    with patch(
        "requests.get",
        side_effect=mocked_exception,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()
        entity = hass.states.get("sensor.radarr_upcoming")
        assert entity is not None
        assert "unavailable" == entity.state
