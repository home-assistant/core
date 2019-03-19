"""The tests for the Radarr platform."""
import unittest

import pytest

import homeassistant.components.radarr.sensor as radarr

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

    url = str(args[0])
    if 'api/calendar' in url:
        return MockResponse([
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
                        "url": ("/radarr/MediaCover/12/poster.jpg"
                                "?lastWrite=636208663600000000")
                    },
                    {
                        "coverType": "banner",
                        "url": ("/radarr/MediaCover/12/banner.jpg"
                                "?lastWrite=636208663600000000")
                    }
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
                "genres": [
                    "Action",
                    "Horror",
                    "Science Fiction"
                ],
                "tags": [],
                "added": "2017-01-24T14:52:39.989964Z",
                "ratings": {
                    "votes": 363,
                    "value": 4.3
                },
                "alternativeTitles": [
                    "Resident Evil: Rising"
                ],
                "qualityProfileId": 3,
                "id": 12
            }
        ], 200)
    if 'api/command' in url:
        return MockResponse([
            {
                "name": "RescanMovie",
                "startedOn": "0001-01-01T00:00:00Z",
                "stateChangeTime": "2014-02-05T05:09:09.2366139Z",
                "sendUpdatesToClient": "true",
                "state": "pending",
                "id": 24
            }
        ], 200)
    if 'api/movie' in url:
        return MockResponse([
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
                        "url": ("/radarr/MediaCover/1/poster.jpg"
                                "?lastWrite=636200219330000000")
                    },
                    {
                        "coverType": "banner",
                        "url": ("/radarr/MediaCover/1/banner.jpg"
                                "?lastWrite=636200219340000000")
                    }
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
                "genres": [
                    "Action",
                    "Adventure",
                    "Fantasy",
                    "Science Fiction"
                ],
                "tags": [],
                "added": "2017-01-14T20:18:52.938244Z",
                "ratings": {
                    "votes": 711,
                    "value": 5.2
                },
                "alternativeTitles": [
                    "Assassin's Creed: The IMAX Experience"
                ],
                "qualityProfileId": 6,
                "id": 1
            }
        ], 200)
    if 'api/diskspace' in url:
        return MockResponse([
            {
                "path": "/data",
                "label": "",
                "freeSpace": 282500067328,
                "totalSpace": 499738734592
            }
        ], 200)
    if 'api/system/status' in url:
        return MockResponse({
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
            "runtimeVersion": ("4.6.1 "
                               "(Stable 4.6.1.3/abb06f1 "
                               "Mon Oct  3 07:57:59 UTC 2016)")
        }, 200)
    return MockResponse({
        "error": "Unauthorized"
    }, 401)


class TestRadarrSetup(unittest.TestCase):
    """Test the Radarr platform."""

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
        self.hass.config.time_zone = 'America/Los_Angeles'

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_diskspace_no_paths(self, req_mock):
        """Test getting all disk space."""
        config = {
            'platform': 'radarr',
            'api_key': 'foo',
            'days': '2',
            'unit': 'GB',
            "include_paths": [],
            'monitored_conditions': [
                'diskspace'
            ]
        }
        radarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert '263.10' == device.state
            assert 'mdi:harddisk' == device.icon
            assert 'GB' == device.unit_of_measurement
            assert 'Radarr Disk Space' == device.name
            assert '263.10/465.42GB (56.53%)' == \
                device.device_state_attributes["/data"]

    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_diskspace_paths(self, req_mock):
        """Test getting diskspace for included paths."""
        config = {
            'platform': 'radarr',
            'api_key': 'foo',
            'days': '2',
            'unit': 'GB',
            "include_paths": [
                '/data'
            ],
            'monitored_conditions': [
                'diskspace'
            ]
        }
        radarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert '263.10' == device.state
            assert 'mdi:harddisk' == device.icon
            assert 'GB' == device.unit_of_measurement
            assert 'Radarr Disk Space' == device.name
            assert '263.10/465.42GB (56.53%)' == \
                device.device_state_attributes["/data"]

    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_commands(self, req_mock):
        """Test getting running commands."""
        config = {
            'platform': 'radarr',
            'api_key': 'foo',
            'days': '2',
            'unit': 'GB',
            "include_paths": [
                '/data'
            ],
            'monitored_conditions': [
                'commands'
            ]
        }
        radarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert 1 == device.state
            assert 'mdi:code-braces' == device.icon
            assert 'Commands' == device.unit_of_measurement
            assert 'Radarr Commands' == device.name
            assert 'pending' == \
                device.device_state_attributes["RescanMovie"]

    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_movies(self, req_mock):
        """Test getting the number of movies."""
        config = {
            'platform': 'radarr',
            'api_key': 'foo',
            'days': '2',
            'unit': 'GB',
            "include_paths": [
                '/data'
            ],
            'monitored_conditions': [
                'movies'
            ]
        }
        radarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert 1 == device.state
            assert 'mdi:television' == device.icon
            assert 'Movies' == device.unit_of_measurement
            assert 'Radarr Movies' == device.name
            assert 'false' == \
                device.device_state_attributes["Assassin's Creed (2016)"]

    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_upcoming_multiple_days(self, req_mock):
        """Test the upcoming movies for multiple days."""
        config = {
            'platform': 'radarr',
            'api_key': 'foo',
            'days': '2',
            'unit': 'GB',
            "include_paths": [
                '/data'
            ],
            'monitored_conditions': [
                'upcoming'
            ]
        }
        radarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert 1 == device.state
            assert 'mdi:television' == device.icon
            assert 'Movies' == device.unit_of_measurement
            assert 'Radarr Upcoming' == device.name
            assert '2017-01-27T00:00:00Z' == \
                device.device_state_attributes["Resident Evil (2017)"]

    @pytest.mark.skip
    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_upcoming_today(self, req_mock):
        """Test filtering for a single day.

        Radarr needs to respond with at least 2 days.
        """
        config = {
            'platform': 'radarr',
            'api_key': 'foo',
            'days': '1',
            'unit': 'GB',
            "include_paths": [
                '/data'
            ],
            'monitored_conditions': [
                'upcoming'
            ]
        }
        radarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert 1 == device.state
            assert 'mdi:television' == device.icon
            assert 'Movies' == device.unit_of_measurement
            assert 'Radarr Upcoming' == device.name
            assert '2017-01-27T00:00:00Z' == \
                device.device_state_attributes["Resident Evil (2017)"]

    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_system_status(self, req_mock):
        """Test the getting of the system status."""
        config = {
            'platform': 'radarr',
            'api_key': 'foo',
            'days': '2',
            'unit': 'GB',
            "include_paths": [
                '/data'
            ],
            'monitored_conditions': [
                'status'
            ]
        }
        radarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert '0.2.0.210' == device.state
            assert 'mdi:information' == device.icon
            assert 'Radarr Status' == device.name
            assert '4.8.13.1' == device.device_state_attributes['osVersion']

    @pytest.mark.skip
    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_ssl(self, req_mock):
        """Test SSL being enabled."""
        config = {
            'platform': 'radarr',
            'api_key': 'foo',
            'days': '1',
            'unit': 'GB',
            "include_paths": [
                '/data'
            ],
            'monitored_conditions': [
                'upcoming'
            ],
            "ssl": "true"
        }
        radarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert 1 == device.state
            assert 's' == device.ssl
            assert 'mdi:television' == device.icon
            assert 'Movies' == device.unit_of_measurement
            assert 'Radarr Upcoming' == device.name
            assert '2017-01-27T00:00:00Z' == \
                device.device_state_attributes["Resident Evil (2017)"]

    @unittest.mock.patch('requests.get', side_effect=mocked_exception)
    def test_exception_handling(self, req_mock):
        """Test exception being handled."""
        config = {
            'platform': 'radarr',
            'api_key': 'foo',
            'days': '1',
            'unit': 'GB',
            "include_paths": [
                '/data'
            ],
            'monitored_conditions': [
                'upcoming'
            ]
        }
        radarr.setup_platform(self.hass, config, self.add_entities, None)
        for device in self.DEVICES:
            device.update()
            assert device.state is None
