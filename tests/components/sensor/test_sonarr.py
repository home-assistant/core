"""The tests for the sonarr platform."""
import unittest
import time
from datetime import datetime
from homeassistant.components.sensor import sonarr

from tests.common import get_test_home_assistant

VALID_CONFIG = {
    'platform': 'sonarr',
    'api_key': 'foo',
    'days': '2',
    'unit': 'GB',
    "include_paths": [
        '/data'
    ],
    'monitored_conditions': [
        'series', 'upcoming', 'wanted', 'queue', 'commands', 'diskspace'
        # 'upcoming'
    ]
}


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
    if 'api/calendar' in str(args[0]):
        return MockResponse([
            {
                "seriesId": 3,
                "episodeFileId": 0,
                "seasonNumber": 4,
                "episodeNumber": 11,
                "title": "Easy Com-mercial, Easy Go-mercial",
                "airDate": str(today),
                "airDateUtc": "2014-01-27T01:30:00Z",
                "overview": "To compete with fellow “restaurateur,” Jimmy Pesto, and his blowout Super Bowl event, Bob is determined to create a Bob’s Burgers commercial to air during the “big game.” In an effort to outshine Pesto, the Belchers recruit Randy, a documentarian, to assist with the filmmaking and hire on former pro football star Connie Frye to be the celebrity endorser.",
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
                  "overview": "Bob's Burgers follows a third-generation restaurateur, Bob, as he runs Bob's Burgers with the help of his wife and their three kids. Bob and his quirky family have big ideas about burgers, but fall short on service and sophistication. Despite the greasy counters, lousy location and a dearth of customers, Bob and his family are determined to make Bob's Burgers \"grand re-re-re-opening\" a success.",
                  "airTime": "5:30pm",
                  "monitored": "true",
                  "qualityProfileId": 1,
                  "seasonFolder": "true",
                  "lastInfoSync": "2014-01-26T19:25:55.4555946Z",
                  "runtime": 30,
                  "images": [
                    {
                      "coverType": "banner",
                      "url": "http://slurm.trakt.us/images/banners/1387.6.jpg"
                    },
                    {
                      "coverType": "poster",
                      "url": "http://slurm.trakt.us/images/posters/1387.6-300.jpg"
                    },
                    {
                      "coverType": "fanart",
                      "url": "http://slurm.trakt.us/images/fanart/1387.6.jpg"
                    }
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
                        {
                          "id": 1,
                          "name": "SDTV",
                          "weight": 1
                        },
                        {
                          "id": 8,
                          "name": "WEBDL-480p",
                          "weight": 2
                        },
                        {
                          "id": 2,
                          "name": "DVD",
                          "weight": 3
                        }
                      ],
                      "cutoff": {
                        "id": 1,
                        "name": "SDTV",
                        "weight": 1
                      },
                      "id": 1
                    },
                    "isLoaded": "true"
                  },
                  "seasons": [
                    {
                      "seasonNumber": 4,
                      "monitored": "true"
                    },
                    {
                      "seasonNumber": 3,
                      "monitored": "true"
                    },
                    {
                      "seasonNumber": 2,
                      "monitored": "true"
                    },
                    {
                      "seasonNumber": 1,
                      "monitored": "true"
                    },
                    {
                      "seasonNumber": 0,
                      "monitored": "false"
                    }
                  ],
                  "id": 66
                },
                "downloading": "false",
                "id": 14402
              }
        ], 200)
    elif 'api/command' in str(args[0]):
        return MockResponse([
            {
              "name": "RescanSeries",
              "startedOn": "0001-01-01T00:00:00Z",
              "stateChangeTime": "2014-02-05T05:09:09.2366139Z",
              "sendUpdatesToClient": "true",
              "state": "pending",
              "id": 24
            }
        ], 200)
    elif 'api/wanted/missing' in str(args[0]) or 'totalRecords' in str(args[0]):
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
              "overview": "Archer has to stage an intervention for Pam that gets derailed by an unwanted guest. ",
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
                "overview": "At ISIS, an international spy agency, global crises are merely opportunities for its highly trained employees to confuse, undermine, betray and royally screw each other. At the center of it all is suave master spy Sterling Archer, whose less-than-masculine code name is \"Duchess.\" Archer works with his domineering mother Malory, who is also his boss. Drama revolves around Archer's ex-girlfriend, Agent Lana Kane and her new boyfriend, ISIS comptroller Cyril Figgis, as well as Malory's lovesick secretary, Cheryl.",
                "airTime": "7:00pm",
                "monitored": "true",
                "qualityProfileId": 1,
                "seasonFolder": "true",
                "lastInfoSync": "2014-02-05T04:39:28.550495Z",
                "runtime": 30,
                "images": [
                  {
                    "coverType": "banner",
                    "url": "http://slurm.trakt.us/images/banners/57.12.jpg"
                  },
                  {
                    "coverType": "poster",
                    "url": "http://slurm.trakt.us/images/posters/57.12-300.jpg"
                  },
                  {
                    "coverType": "fanart",
                    "url": "http://slurm.trakt.us/images/fanart/57.12.jpg"
                  }
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
                    "cutoff": {
                      "id": 1,
                      "name": "SDTV"
                    },
                    "items": [
                      {
                        "quality": {
                          "id": 1,
                          "name": "SDTV"
                        },
                        "allowed": "true"
                      },
                      {
                        "quality": {
                          "id": 8,
                          "name": "WEBDL-480p"
                        },
                        "allowed": "true"
                      },
                      {
                        "quality": {
                          "id": 2,
                          "name": "DVD"
                        },
                        "allowed": "true"
                      },
                      {
                        "quality": {
                          "id": 4,
                          "name": "HDTV-720p"
                        },
                        "allowed": "false"
                      },
                      {
                        "quality": {
                          "id": 9,
                          "name": "HDTV-1080p"
                        },
                        "allowed": "false"
                      },
                      {
                        "quality": {
                          "id": 10,
                          "name": "Raw-HD"
                        },
                        "allowed": "false"
                      },
                      {
                        "quality": {
                          "id": 5,
                          "name": "WEBDL-720p"
                        },
                        "allowed": "false"
                      },
                      {
                        "quality": {
                          "id": 6,
                          "name": "Bluray-720p"
                        },
                        "allowed": "false"
                      },
                      {
                        "quality": {
                          "id": 3,
                          "name": "WEBDL-1080p"
                        },
                        "allowed": "false"
                      },
                      {
                        "quality": {
                          "id": 7,
                          "name": "Bluray-1080p"
                        },
                        "allowed": "false"
                      }
                    ],
                    "id": 1
                  },
                  "isLoaded": "true"
                },
                "seasons": [
                  {
                    "seasonNumber": 5,
                    "monitored": "true"
                  },
                  {
                    "seasonNumber": 4,
                    "monitored": "true"
                  },
                  {
                    "seasonNumber": 3,
                    "monitored": "true"
                  },
                  {
                    "seasonNumber": 2,
                    "monitored": "true"
                  },
                  {
                    "seasonNumber": 1,
                    "monitored": "true"
                  },
                  {
                    "seasonNumber": 0,
                    "monitored": "false"
                  }
                ],
                "id": 1
              },
              "downloading": "false",
              "id": 55
            }
          ]
        }, 200)
    elif 'api/queue' in str(args[0]):
        return MockResponse([
          {
            "series": {
              "title": "Game of Thrones",
              "sortTitle": "game thrones",
              "seasonCount": 6,
              "status": "continuing",
              "overview": "Seven noble families fight for control of the mythical land of Westeros. Friction between the houses leads to full-scale war. All while a very ancient evil awakens in the farthest north. Amidst the war, a neglected military order of misfits, the Night's Watch, is all that stands between the realms of men and the icy horrors beyond.",
              "network": "HBO",
              "airTime": "21:00",
              "images": [
                {
                  "coverType": "fanart",
                  "url": "http://thetvdb.com/banners/fanart/original/121361-83.jpg"
                },
                {
                  "coverType": "banner",
                  "url": "http://thetvdb.com/banners/graphical/121361-g19.jpg"
                },
                {
                  "coverType": "poster",
                  "url": "http://thetvdb.com/banners/posters/121361-34.jpg"
                }
              ],
              "seasons": [
                {
                  "seasonNumber": 0,
                  "monitored": "false"
                },
                {
                  "seasonNumber": 1,
                  "monitored": "false"
                },
                {
                  "seasonNumber": 2,
                  "monitored": "true"
                },
                {
                  "seasonNumber": 3,
                  "monitored": "false"
                },
                {
                  "seasonNumber": 4,
                  "monitored": "false"
                },
                {
                  "seasonNumber": 5,
                  "monitored": "true"
                },
                {
                  "seasonNumber": 6,
                  "monitored": "true"
                }
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
              "genres": [
                "Adventure",
                "Drama",
                "Fantasy"
              ],
              "tags": [],
              "added": "2015-12-28T13:44:24.204583Z",
              "ratings": {
                "votes": 1128,
                "value": 9.4
              },
              "qualityProfileId": 5,
              "id": 17
            },
            "episode": {
              "seriesId": 17,
              "episodeFileId": 0,
              "seasonNumber": 3,
              "episodeNumber": 8,
              "title": "Second Sons",
              "airDate": "2013-05-19",
              "airDateUtc": "2013-05-20T01:00:00Z",
              "overview": "King’s Landing hosts a wedding, and Tyrion and Sansa spend the night together. Daenerys meets the Titan’s Bastard. Davos demands proof from Melisandre. Sam and Gilly meet an older gentleman.",
              "hasFile": "false",
              "monitored": "false",
              "absoluteEpisodeNumber": 28,
              "unverifiedSceneNumbering": "false",
              "id": 889
            },
            "quality": {
              "quality": {
                "id": 7,
                "name": "Bluray-1080p"
              },
              "revision": {
                "version": 1,
                "real": 0
              }
            },
            "size": 4472186820,
            "title": "Game.of.Thrones.S03E08.Second.Sons.2013.1080p.BluRay.Dts.x264-CYTSUNEE-Obfuscated",
            "sizeleft": 0,
            "timeleft": "00:00:00",
            "estimatedCompletionTime": "2016-02-05T22:46:52.440104Z",
            "status": "Downloading",
            "trackedDownloadStatus": "Ok",
            "statusMessages": [],
            "downloadId": "SABnzbd_nzo_Mq2f_b",
            "protocol": "usenet",
            "id": 1503378561
          }
        ], 200)
    elif 'api/series' in str(args[0]):
        return MockResponse([
          {
            "title": "Marvel's Daredevil",
            "alternateTitles": [{
              "title": "Daredevil",
              "seasonNumber": -1
            }],
            "sortTitle": "marvels daredevil",
            "seasonCount": 2,
            "totalEpisodeCount": 26,
            "episodeCount": 26,
            "episodeFileCount": 26,
            "sizeOnDisk": 79282273693,
            "status": "continuing",
            "overview": "Matt Murdock was blinded in a tragic accident as a boy, but imbued with extraordinary senses. Murdock sets up practice in his old neighborhood of Hell's Kitchen, New York, where he now fights against injustice as a respected lawyer by day and as the masked vigilante Daredevil by night.",
            "previousAiring": "2016-03-18T04:01:00Z",
            "network": "Netflix",
            "airTime": "00:01",
            "images": [{
              "coverType": "fanart",
              "url": "/sonarr/MediaCover/7/fanart.jpg?lastWrite=636072351904299472"
            },
            {
              "coverType": "banner",
              "url": "/sonarr/MediaCover/7/banner.jpg?lastWrite=636071666185812942"
            },
            {
              "coverType": "poster",
              "url": "/sonarr/MediaCover/7/poster.jpg?lastWrite=636071666195067584"
            }],
            "seasons": [{
              "seasonNumber": 1,
              "monitored": "false",
              "statistics": {
                "previousAiring": "2015-04-10T04:01:00Z",
                "episodeFileCount": 13,
                "episodeCount": 13,
                "totalEpisodeCount": 13,
                "sizeOnDisk": 22738179333,
                "percentOfEpisodes": 100
              }
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
                "percentOfEpisodes": 100
              }
            }],
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
            "genres": ["Action",
            "Crime",
            "Drama"],
            "tags": [],
            "added": "2015-05-15T00:20:32.7892744Z",
            "ratings": {
              "votes": 461,
              "value": 8.9
            },
            "qualityProfileId": 6,
            "id": 7
          }
        ], 200)
    elif 'api/diskspace' in str(args[0]):
        return MockResponse([
          {
            "path": "/data",
            "label": "",
            "freeSpace": 282500067328,
            "totalSpace": 499738734592
          }
        ], 200)
    else:
        return MockResponse({
            "error": "Unauthorized"
        }, 401)


class TestSonarrSetup(unittest.TestCase):
    """Test the Sonarr platform."""

    # pylint: disable=invalid-name
    DEVICES = []

    def add_devices(self, devices):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.DEVICES = []
        self.hass = get_test_home_assistant()
        self.hass.config.time_zone = 'America/Los_Angeles'

    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_diskspace_no_paths(self, req_mock):
        config = {
            'platform': 'sonarr',
            'api_key': 'foo',
            'days': '2',
            'unit': 'GB',
            "include_paths": [],
            'monitored_conditions': [
                'diskspace'
            ]
        }
        sonarr.setup_platform(self.hass, config, self.add_devices,
                                    None)
        for device in self.DEVICES:
            device.update()
            self.assertEqual('263.10', device.state)
            self.assertEqual('mdi:harddisk', device.icon)
            self.assertEqual('GB', device.unit_of_measurement)
            self.assertEqual('Sonarr Disk Space', device.name)
            self.assertEqual('263.10/465.42GB (56.53%)', device.device_state_attributes["/data"])

    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_diskspace_paths(self, req_mock):
        config = {
            'platform': 'sonarr',
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
        sonarr.setup_platform(self.hass, config, self.add_devices,
                                    None)
        for device in self.DEVICES:
            device.update()
            self.assertEqual('263.10', device.state)
            self.assertEqual('mdi:harddisk', device.icon)
            self.assertEqual('GB', device.unit_of_measurement)
            self.assertEqual('Sonarr Disk Space', device.name)
            self.assertEqual('263.10/465.42GB (56.53%)', device.device_state_attributes["/data"])

    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_commands(self, req_mock):
        config = {
            'platform': 'sonarr',
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
        sonarr.setup_platform(self.hass, config, self.add_devices,
                                    None)
        for device in self.DEVICES:
            device.update()
            self.assertEqual(1, device.state)
            self.assertEqual('mdi:code-braces', device.icon)
            self.assertEqual('Commands', device.unit_of_measurement)
            self.assertEqual('Sonarr Commands', device.name)
            self.assertEqual('pending', device.device_state_attributes["RescanSeries"])

    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_queue(self, req_mock):
        config = {
            'platform': 'sonarr',
            'api_key': 'foo',
            'days': '2',
            'unit': 'GB',
            "include_paths": [
                '/data'
            ],
            'monitored_conditions': [
                'queue'
            ]
        }
        sonarr.setup_platform(self.hass, config, self.add_devices,
                                    None)
        for device in self.DEVICES:
            device.update()
            self.assertEqual(1, device.state)
            self.assertEqual('mdi:download', device.icon)
            self.assertEqual('Episodes', device.unit_of_measurement)
            self.assertEqual('Sonarr Queue', device.name)
            self.assertEqual('100.00%', device.device_state_attributes["Game of Thrones S03E08"])

    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_series(self, req_mock):
        config = {
            'platform': 'sonarr',
            'api_key': 'foo',
            'days': '2',
            'unit': 'GB',
            "include_paths": [
                '/data'
            ],
            'monitored_conditions': [
                'series'
            ]
        }
        sonarr.setup_platform(self.hass, config, self.add_devices,
                                    None)
        for device in self.DEVICES:
            device.update()
            self.assertEqual(1, device.state)
            self.assertEqual('mdi:television', device.icon)
            self.assertEqual('Shows', device.unit_of_measurement)
            self.assertEqual('Sonarr Series', device.name)
            self.assertEqual('26/26 Episodes', device.device_state_attributes["Marvel's Daredevil"])

    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_wanted(self, req_mock):
        config = {
            'platform': 'sonarr',
            'api_key': 'foo',
            'days': '2',
            'unit': 'GB',
            "include_paths": [
                '/data'
            ],
            'monitored_conditions': [
                'wanted'
            ]
        }
        sonarr.setup_platform(self.hass, config, self.add_devices,
                                    None)
        for device in self.DEVICES:
            device.update()
            self.assertEqual(1, device.state)
            self.assertEqual('mdi:television', device.icon)
            self.assertEqual('Episodes', device.unit_of_measurement)
            self.assertEqual('Sonarr Wanted', device.name)
            self.assertEqual('2014-02-03', device.device_state_attributes["Archer (2009) S05E04"])

    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_upcoming_multiple_days(self, req_mock):
        config = {
            'platform': 'sonarr',
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
        sonarr.setup_platform(self.hass, config, self.add_devices,
                                    None)
        for device in self.DEVICES:
            device.update()
            self.assertEqual(1, device.state)
            self.assertEqual('mdi:television', device.icon)
            self.assertEqual('Episodes', device.unit_of_measurement)
            self.assertEqual('Sonarr Upcoming', device.name)
            self.assertEqual('S04E11', device.device_state_attributes["Bob's Burgers"])

    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_upcoming_today(self, req_mock):
        config = {
            'platform': 'sonarr',
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
        sonarr.setup_platform(self.hass, config, self.add_devices,
                                    None)
        for device in self.DEVICES:
            device.update()
            self.assertEqual(1, device.state)
            self.assertEqual('mdi:television', device.icon)
            self.assertEqual('Episodes', device.unit_of_measurement)
            self.assertEqual('Sonarr Upcoming', device.name)
            self.assertEqual('S04E11', device.device_state_attributes["Bob's Burgers"])

    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_ssl(self, req_mock):
        config = {
            'platform': 'sonarr',
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
        sonarr.setup_platform(self.hass, config, self.add_devices,
                                    None)
        for device in self.DEVICES:
            device.update()
            self.assertEqual(1, device.state)
            self.assertEqual('s', device.ssl)
            self.assertEqual('mdi:television', device.icon)
            self.assertEqual('Episodes', device.unit_of_measurement)
            self.assertEqual('Sonarr Upcoming', device.name)
            self.assertEqual('S04E11', device.device_state_attributes["Bob's Burgers"])
