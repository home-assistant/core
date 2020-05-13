"""The tests for the Sonarr platform."""
from datetime import datetime
import time
import unittest

import pytest

import homeassistant.components.sonarr.sensor as sonarr
from homeassistant.const import DATA_GIGABYTES, UNIT_PERCENTAGE

from tests.async_mock import patch
from tests.common import get_test_home_assistant


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

    today = datetime.date(datetime.fromtimestamp(time.time()))
    url = str(args[0])
    if "api/calendar" in url:
        return MockResponse(
            [
                {
                    "seriesId": 3,
                    "episodeFileId": 0,
                    "seasonNumber": 4,
                    "episodeNumber": 11,
                    "title": "Easy Com-mercial, Easy Go-mercial",
                    "airDate": str(today),
                    "airDateUtc": "2014-01-27T01:30:00Z",
                    "overview": "To compete with fellow “restaurateur,” Ji...",
                    "hasFile": "false",
                    "monitored": "true",
                    "sceneEpisodeNumber": 0,
                    "sceneSeasonNumber": 0,
                    "tvDbEpisodeId": 0,
                    "series": {
                        "tvdbId": 194031,
                        "tvRageId": 24607,
                        "imdbId": "tt1561755",
                        "title": "Bob's Burgers",
                        "cleanTitle": "bobsburgers",
                        "status": "continuing",
                        "overview": "Bob's Burgers follows a third-generation ...",
                        "airTime": "5:30pm",
                        "monitored": "true",
                        "qualityProfileId": 1,
                        "seasonFolder": "true",
                        "lastInfoSync": "2014-01-26T19:25:55.4555946Z",
                        "runtime": 30,
                        "images": [
                            {
                                "coverType": "banner",
                                "url": "http://slurm.trakt.us/images/bann.jpg",
                            },
                            {
                                "coverType": "poster",
                                "url": "http://slurm.trakt.us/images/poster00.jpg",
                            },
                            {
                                "coverType": "fanart",
                                "url": "http://slurm.trakt.us/images/fan6.jpg",
                            },
                        ],
                        "seriesType": "standard",
                        "network": "FOX",
                        "useSceneNumbering": "false",
                        "titleSlug": "bobs-burgers",
                        "path": "T:\\Bob's Burgers",
                        "year": 0,
                        "firstAired": "2011-01-10T01:30:00Z",
                        "qualityProfile": {
                            "value": {
                                "name": "SD",
                                "allowed": [
                                    {"id": 1, "name": "SDTV", "weight": 1},
                                    {"id": 8, "name": "WEBDL-480p", "weight": 2},
                                    {"id": 2, "name": "DVD", "weight": 3},
                                ],
                                "cutoff": {"id": 1, "name": "SDTV", "weight": 1},
                                "id": 1,
                            },
                            "isLoaded": "true",
                        },
                        "seasons": [
                            {"seasonNumber": 4, "monitored": "true"},
                            {"seasonNumber": 3, "monitored": "true"},
                            {"seasonNumber": 2, "monitored": "true"},
                            {"seasonNumber": 1, "monitored": "true"},
                            {"seasonNumber": 0, "monitored": "false"},
                        ],
                        "id": 66,
                    },
                    "downloading": "false",
                    "id": 14402,
                }
            ],
            200,
        )
    if "api/command" in url:
        return MockResponse(
            [
                {
                    "name": "RescanSeries",
                    "startedOn": "0001-01-01T00:00:00Z",
                    "stateChangeTime": "2014-02-05T05:09:09.2366139Z",
                    "sendUpdatesToClient": "true",
                    "state": "pending",
                    "id": 24,
                }
            ],
            200,
        )
    if "api/wanted/missing" in url or "totalRecords" in url:
        return MockResponse(
            {
                "page": 1,
                "pageSize": 15,
                "sortKey": "airDateUtc",
                "sortDirection": "descending",
                "totalRecords": 1,
                "records": [
                    {
                        "seriesId": 1,
                        "episodeFileId": 0,
                        "seasonNumber": 5,
                        "episodeNumber": 4,
                        "title": "Archer Vice: House Call",
                        "airDate": "2014-02-03",
                        "airDateUtc": "2014-02-04T03:00:00Z",
                        "overview": "Archer has to stage an  that ... ",
                        "hasFile": "false",
                        "monitored": "true",
                        "sceneEpisodeNumber": 0,
                        "sceneSeasonNumber": 0,
                        "tvDbEpisodeId": 0,
                        "absoluteEpisodeNumber": 50,
                        "series": {
                            "tvdbId": 110381,
                            "tvRageId": 23354,
                            "imdbId": "tt1486217",
                            "title": "Archer (2009)",
                            "cleanTitle": "archer2009",
                            "status": "continuing",
                            "overview": "At ISIS, an international spy ...",
                            "airTime": "7:00pm",
                            "monitored": "true",
                            "qualityProfileId": 1,
                            "seasonFolder": "true",
                            "lastInfoSync": "2014-02-05T04:39:28.550495Z",
                            "runtime": 30,
                            "images": [
                                {
                                    "coverType": "banner",
                                    "url": "http://slurm.trakt.us//57.12.jpg",
                                },
                                {
                                    "coverType": "poster",
                                    "url": "http://slurm.trakt.u/57.12-300.jpg",
                                },
                                {
                                    "coverType": "fanart",
                                    "url": "http://slurm.trakt.us/image.12.jpg",
                                },
                            ],
                            "seriesType": "standard",
                            "network": "FX",
                            "useSceneNumbering": "false",
                            "titleSlug": "archer-2009",
                            "path": "E:\\Test\\TV\\Archer (2009)",
                            "year": 2009,
                            "firstAired": "2009-09-18T02:00:00Z",
                            "qualityProfile": {
                                "value": {
                                    "name": "SD",
                                    "cutoff": {"id": 1, "name": "SDTV"},
                                    "items": [
                                        {
                                            "quality": {"id": 1, "name": "SDTV"},
                                            "allowed": "true",
                                        },
                                        {
                                            "quality": {"id": 8, "name": "WEBDL-480p"},
                                            "allowed": "true",
                                        },
                                        {
                                            "quality": {"id": 2, "name": "DVD"},
                                            "allowed": "true",
                                        },
                                        {
                                            "quality": {"id": 4, "name": "HDTV-720p"},
                                            "allowed": "false",
                                        },
                                        {
                                            "quality": {"id": 9, "name": "HDTV-1080p"},
                                            "allowed": "false",
                                        },
                                        {
                                            "quality": {"id": 10, "name": "Raw-HD"},
                                            "allowed": "false",
                                        },
                                        {
                                            "quality": {"id": 5, "name": "WEBDL-720p"},
                                            "allowed": "false",
                                        },
                                        {
                                            "quality": {"id": 6, "name": "Bluray-720p"},
                                            "allowed": "false",
                                        },
                                        {
                                            "quality": {"id": 3, "name": "WEBDL-1080p"},
                                            "allowed": "false",
                                        },
                                        {
                                            "quality": {
                                                "id": 7,
                                                "name": "Bluray-1080p",
                                            },
                                            "allowed": "false",
                                        },
                                    ],
                                    "id": 1,
                                },
                                "isLoaded": "true",
                            },
                            "seasons": [
                                {"seasonNumber": 5, "monitored": "true"},
                                {"seasonNumber": 4, "monitored": "true"},
                                {"seasonNumber": 3, "monitored": "true"},
                                {"seasonNumber": 2, "monitored": "true"},
                                {"seasonNumber": 1, "monitored": "true"},
                                {"seasonNumber": 0, "monitored": "false"},
                            ],
                            "id": 1,
                        },
                        "downloading": "false",
                        "id": 55,
                    }
                ],
            },
            200,
        )
    if "api/queue" in url:
        return MockResponse(
            [
                {
                    "series": {
                        "title": "Game of Thrones",
                        "sortTitle": "game thrones",
                        "seasonCount": 6,
                        "status": "continuing",
                        "overview": "Seven noble families fight for  land ...",
                        "network": "HBO",
                        "airTime": "21:00",
                        "images": [
                            {
                                "coverType": "fanart",
                                "url": "http://thetvdb.com/banners/fanart/-83.jpg",
                            },
                            {
                                "coverType": "banner",
                                "url": "http://thetvdb.com/banners/-g19.jpg",
                            },
                            {
                                "coverType": "poster",
                                "url": "http://thetvdb.com/banners/posters-34.jpg",
                            },
                        ],
                        "seasons": [
                            {"seasonNumber": 0, "monitored": "false"},
                            {"seasonNumber": 1, "monitored": "false"},
                            {"seasonNumber": 2, "monitored": "true"},
                            {"seasonNumber": 3, "monitored": "false"},
                            {"seasonNumber": 4, "monitored": "false"},
                            {"seasonNumber": 5, "monitored": "true"},
                            {"seasonNumber": 6, "monitored": "true"},
                        ],
                        "year": 2011,
                        "path": "/Volumes/Media/Shows/Game of Thrones",
                        "profileId": 5,
                        "seasonFolder": "true",
                        "monitored": "true",
                        "useSceneNumbering": "false",
                        "runtime": 60,
                        "tvdbId": 121361,
                        "tvRageId": 24493,
                        "tvMazeId": 82,
                        "firstAired": "2011-04-16T23:00:00Z",
                        "lastInfoSync": "2016-02-05T16:40:11.614176Z",
                        "seriesType": "standard",
                        "cleanTitle": "gamethrones",
                        "imdbId": "tt0944947",
                        "titleSlug": "game-of-thrones",
                        "certification": "TV-MA",
                        "genres": ["Adventure", "Drama", "Fantasy"],
                        "tags": [],
                        "added": "2015-12-28T13:44:24.204583Z",
                        "ratings": {"votes": 1128, "value": 9.4},
                        "qualityProfileId": 5,
                        "id": 17,
                    },
                    "episode": {
                        "seriesId": 17,
                        "episodeFileId": 0,
                        "seasonNumber": 3,
                        "episodeNumber": 8,
                        "title": "Second Sons",
                        "airDate": "2013-05-19",
                        "airDateUtc": "2013-05-20T01:00:00Z",
                        "overview": "King’s Landing hosts a wedding, and  ...",
                        "hasFile": "false",
                        "monitored": "false",
                        "absoluteEpisodeNumber": 28,
                        "unverifiedSceneNumbering": "false",
                        "id": 889,
                    },
                    "quality": {
                        "quality": {"id": 7, "name": "Bluray-1080p"},
                        "revision": {"version": 1, "real": 0},
                    },
                    "size": 4472186820,
                    "title": "Game.of.Thrones.S03E08.Second.Sons.2013.1080p.",
                    "sizeleft": 0,
                    "timeleft": "00:00:00",
                    "estimatedCompletionTime": "2016-02-05T22:46:52.440104Z",
                    "status": "Downloading",
                    "trackedDownloadStatus": "Ok",
                    "statusMessages": [],
                    "downloadId": "SABnzbd_nzo_Mq2f_b",
                    "protocol": "usenet",
                    "id": 1503378561,
                }
            ],
            200,
        )
    if "api/series" in url:
        return MockResponse(
            [
                {
                    "title": "Marvel's Daredevil",
                    "alternateTitles": [{"title": "Daredevil", "seasonNumber": -1}],
                    "sortTitle": "marvels daredevil",
                    "seasonCount": 2,
                    "totalEpisodeCount": 26,
                    "episodeCount": 26,
                    "episodeFileCount": 26,
                    "sizeOnDisk": 79282273693,
                    "status": "continuing",
                    "overview": "Matt Murdock was blinded in a tragic accident...",
                    "previousAiring": "2016-03-18T04:01:00Z",
                    "network": "Netflix",
                    "airTime": "00:01",
                    "images": [
                        {
                            "coverType": "fanart",
                            "url": "/sonarr/MediaCover/7/fanart.jpg?lastWrite=",
                        },
                        {
                            "coverType": "banner",
                            "url": "/sonarr/MediaCover/7/banner.jpg?lastWrite=",
                        },
                        {
                            "coverType": "poster",
                            "url": "/sonarr/MediaCover/7/poster.jpg?lastWrite=",
                        },
                    ],
                    "seasons": [
                        {
                            "seasonNumber": 1,
                            "monitored": "false",
                            "statistics": {
                                "previousAiring": "2015-04-10T04:01:00Z",
                                "episodeFileCount": 13,
                                "episodeCount": 13,
                                "totalEpisodeCount": 13,
                                "sizeOnDisk": 22738179333,
                                "percentOfEpisodes": 100,
                            },
                        },
                        {
                            "seasonNumber": 2,
                            "monitored": "false",
                            "statistics": {
                                "previousAiring": "2016-03-18T04:01:00Z",
                                "episodeFileCount": 13,
                                "episodeCount": 13,
                                "totalEpisodeCount": 13,
                                "sizeOnDisk": 56544094360,
                                "percentOfEpisodes": 100,
                            },
                        },
                    ],
                    "year": 2015,
                    "path": "F:\\TV_Shows\\Marvels Daredevil",
                    "profileId": 6,
                    "seasonFolder": "true",
                    "monitored": "true",
                    "useSceneNumbering": "false",
                    "runtime": 55,
                    "tvdbId": 281662,
                    "tvRageId": 38796,
                    "tvMazeId": 1369,
                    "firstAired": "2015-04-10T04:00:00Z",
                    "lastInfoSync": "2016-09-09T09:02:49.4402575Z",
                    "seriesType": "standard",
                    "cleanTitle": "marvelsdaredevil",
                    "imdbId": "tt3322312",
                    "titleSlug": "marvels-daredevil",
                    "certification": "TV-MA",
                    "genres": ["Action", "Crime", "Drama"],
                    "tags": [],
                    "added": "2015-05-15T00:20:32.7892744Z",
                    "ratings": {"votes": 461, "value": 8.9},
                    "qualityProfileId": 6,
                    "id": 7,
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
                "version": "2.0.0.1121",
                "buildTime": "2014-02-08T20:49:36.5560392Z",
                "isDebug": "false",
                "isProduction": "true",
                "isAdmin": "true",
                "isUserInteractive": "false",
                "startupPath": "C:\\ProgramData\\NzbDrone\\bin",
                "appData": "C:\\ProgramData\\NzbDrone",
                "osVersion": "6.2.9200.0",
                "isMono": "false",
                "isLinux": "false",
                "isWindows": "true",
                "branch": "develop",
                "authentication": "false",
                "startOfWeek": 0,
                "urlBase": "",
            },
            200,
        )
    return MockResponse({"error": "Unauthorized"}, 401)


class TestSonarrSetup(unittest.TestCase):
    """Test the Sonarr platform."""

    # pylint: disable=invalid-name
    DEVICES = []

    def add_entities(self, devices, update):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.DEVICES = []
        self.hass = get_test_home_assistant()
        self.hass.config.time_zone = "America/Los_Angeles"

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @patch("requests.get", side_effect=mocked_requests_get)
    def test_diskspace_no_paths(self, req_mock):
        """Test getting all disk space."""
        config = {
            "platform": "sonarr",
            "api_key": "foo",
            "days": "2",
            "unit": DATA_GIGABYTES,
            "include_paths": [],
            "monitored_conditions": ["diskspace"],
        }
        sonarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert "263.10" == device.state
            assert "mdi:harddisk" == device.icon
            assert DATA_GIGABYTES == device.unit_of_measurement
            assert "Sonarr Disk Space" == device.name
            assert "263.10/465.42GB (56.53%)" == device.device_state_attributes["/data"]

    @patch("requests.get", side_effect=mocked_requests_get)
    def test_diskspace_paths(self, req_mock):
        """Test getting diskspace for included paths."""
        config = {
            "platform": "sonarr",
            "api_key": "foo",
            "days": "2",
            "unit": DATA_GIGABYTES,
            "include_paths": ["/data"],
            "monitored_conditions": ["diskspace"],
        }
        sonarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert "263.10" == device.state
            assert "mdi:harddisk" == device.icon
            assert DATA_GIGABYTES == device.unit_of_measurement
            assert "Sonarr Disk Space" == device.name
            assert "263.10/465.42GB (56.53%)" == device.device_state_attributes["/data"]

    @patch("requests.get", side_effect=mocked_requests_get)
    def test_commands(self, req_mock):
        """Test getting running commands."""
        config = {
            "platform": "sonarr",
            "api_key": "foo",
            "days": "2",
            "unit": DATA_GIGABYTES,
            "include_paths": ["/data"],
            "monitored_conditions": ["commands"],
        }
        sonarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert 1 == device.state
            assert "mdi:code-braces" == device.icon
            assert "Commands" == device.unit_of_measurement
            assert "Sonarr Commands" == device.name
            assert "pending" == device.device_state_attributes["RescanSeries"]

    @patch("requests.get", side_effect=mocked_requests_get)
    def test_queue(self, req_mock):
        """Test getting downloads in the queue."""
        config = {
            "platform": "sonarr",
            "api_key": "foo",
            "days": "2",
            "unit": DATA_GIGABYTES,
            "include_paths": ["/data"],
            "monitored_conditions": ["queue"],
        }
        sonarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert 1 == device.state
            assert "mdi:download" == device.icon
            assert "Episodes" == device.unit_of_measurement
            assert "Sonarr Queue" == device.name
            assert (
                f"100.00{UNIT_PERCENTAGE}"
                == device.device_state_attributes["Game of Thrones S03E08"]
            )

    @patch("requests.get", side_effect=mocked_requests_get)
    def test_series(self, req_mock):
        """Test getting the number of series."""
        config = {
            "platform": "sonarr",
            "api_key": "foo",
            "days": "2",
            "unit": DATA_GIGABYTES,
            "include_paths": ["/data"],
            "monitored_conditions": ["series"],
        }
        sonarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert 1 == device.state
            assert "mdi:television" == device.icon
            assert "Shows" == device.unit_of_measurement
            assert "Sonarr Series" == device.name
            assert (
                "26/26 Episodes" == device.device_state_attributes["Marvel's Daredevil"]
            )

    @patch("requests.get", side_effect=mocked_requests_get)
    def test_wanted(self, req_mock):
        """Test getting wanted episodes."""
        config = {
            "platform": "sonarr",
            "api_key": "foo",
            "days": "2",
            "unit": DATA_GIGABYTES,
            "include_paths": ["/data"],
            "monitored_conditions": ["wanted"],
        }
        sonarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert 1 == device.state
            assert "mdi:television" == device.icon
            assert "Episodes" == device.unit_of_measurement
            assert "Sonarr Wanted" == device.name
            assert (
                "2014-02-03" == device.device_state_attributes["Archer (2009) S05E04"]
            )

    @patch("requests.get", side_effect=mocked_requests_get)
    def test_upcoming_multiple_days(self, req_mock):
        """Test the upcoming episodes for multiple days."""
        config = {
            "platform": "sonarr",
            "api_key": "foo",
            "days": "2",
            "unit": DATA_GIGABYTES,
            "include_paths": ["/data"],
            "monitored_conditions": ["upcoming"],
        }
        sonarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert 1 == device.state
            assert "mdi:television" == device.icon
            assert "Episodes" == device.unit_of_measurement
            assert "Sonarr Upcoming" == device.name
            assert "S04E11" == device.device_state_attributes["Bob's Burgers"]

    @pytest.mark.skip
    @patch("requests.get", side_effect=mocked_requests_get)
    def test_upcoming_today(self, req_mock):
        """Test filtering for a single day.

        Sonarr needs to respond with at least 2 days
        """
        config = {
            "platform": "sonarr",
            "api_key": "foo",
            "days": "1",
            "unit": DATA_GIGABYTES,
            "include_paths": ["/data"],
            "monitored_conditions": ["upcoming"],
        }
        sonarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert 1 == device.state
            assert "mdi:television" == device.icon
            assert "Episodes" == device.unit_of_measurement
            assert "Sonarr Upcoming" == device.name
            assert "S04E11" == device.device_state_attributes["Bob's Burgers"]

    @patch("requests.get", side_effect=mocked_requests_get)
    def test_system_status(self, req_mock):
        """Test getting system status."""
        config = {
            "platform": "sonarr",
            "api_key": "foo",
            "days": "2",
            "unit": DATA_GIGABYTES,
            "include_paths": ["/data"],
            "monitored_conditions": ["status"],
        }
        sonarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert "2.0.0.1121" == device.state
            assert "mdi:information" == device.icon
            assert "Sonarr Status" == device.name
            assert "6.2.9200.0" == device.device_state_attributes["osVersion"]

    @pytest.mark.skip
    @patch("requests.get", side_effect=mocked_requests_get)
    def test_ssl(self, req_mock):
        """Test SSL being enabled."""
        config = {
            "platform": "sonarr",
            "api_key": "foo",
            "days": "1",
            "unit": DATA_GIGABYTES,
            "include_paths": ["/data"],
            "monitored_conditions": ["upcoming"],
            "ssl": "true",
        }
        sonarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert 1 == device.state
            assert "s" == device.ssl
            assert "mdi:television" == device.icon
            assert "Episodes" == device.unit_of_measurement
            assert "Sonarr Upcoming" == device.name
            assert "S04E11" == device.device_state_attributes["Bob's Burgers"]

    @patch("requests.get", side_effect=mocked_exception)
    def test_exception_handling(self, req_mock):
        """Test exception being handled."""
        config = {
            "platform": "sonarr",
            "api_key": "foo",
            "days": "1",
            "unit": DATA_GIGABYTES,
            "include_paths": ["/data"],
            "monitored_conditions": ["upcoming"],
        }
        sonarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert device.state is None
