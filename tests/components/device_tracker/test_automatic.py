"""Test the automatic device tracker platform."""

import logging
import requests
import unittest
from unittest.mock import patch

from homeassistant.components.device_tracker.automatic import (
    URL_AUTHORIZE, URL_VEHICLES, URL_TRIPS, setup_scanner)

from tests.common import get_test_home_assistant

_LOGGER = logging.getLogger(__name__)

INVALID_USERNAME = 'bob'
VALID_USERNAME = 'jim'
PASSWORD = 'password'
CLIENT_ID = '12345'
CLIENT_SECRET = '54321'
FUEL_LEVEL = 77.2
LATITUDE = 32.82336
LONGITUDE = -117.23743
ACCURACY = 8
DISPLAY_NAME = 'My Vehicle'


def mocked_requests(*args, **kwargs):
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

        @property
        def content(self):
            """Return the content of the response."""
            return self.json()

        def raise_for_status(self):
            """Raise an HTTPError if status is not 200."""
            if self.status_code != 200:
                raise requests.HTTPError(self.status_code)

    data = kwargs.get('data')

    if data and data.get('username', None) == INVALID_USERNAME:
        return MockResponse({
            "error": "invalid_credentials"
        }, 401)
    elif str(args[0]).startswith(URL_AUTHORIZE):
        return MockResponse({
            "user": {
                "sid": "sid",
                "id": "id"
            },
            "token_type": "Bearer",
            "access_token": "accesstoken",
            "refresh_token": "refreshtoken",
            "expires_in": 31521669,
            "scope": ""
        }, 200)
    elif str(args[0]).startswith(URL_VEHICLES):
        return MockResponse({
            "_metadata": {
                "count": 2,
                "next": None,
                "previous": None
            },
            "results": [
                {
                    "url": "https://api.automatic.com/vehicle/vid/",
                    "id": "vid",
                    "created_at": "2016-03-05T20:05:16.240000Z",
                    "updated_at": "2016-08-29T01:52:59.597898Z",
                    "make": "Honda",
                    "model": "Element",
                    "year": 2007,
                    "submodel": "EX",
                    "display_name": DISPLAY_NAME,
                    "fuel_grade": "regular",
                    "fuel_level_percent": FUEL_LEVEL,
                    "active_dtcs": []
                }]
        }, 200)
    elif str(args[0]).startswith(URL_TRIPS):
        return MockResponse({
            "_metadata": {
                "count": 1594,
                "next": "https://api.automatic.com/trip/?page=2",
                "previous": None
            },
            "results": [
                {
                    "url": "https://api.automatic.com/trip/tid1/",
                    "id": "tid1",
                    "driver": "https://api.automatic.com/user/uid/",
                    "user": "https://api.automatic.com/user/uid/",
                    "started_at": "2016-08-28T19:37:23.986000Z",
                    "ended_at": "2016-08-28T19:43:22.500000Z",
                    "distance_m": 3931.6,
                    "duration_s": 358.5,
                    "vehicle": "https://api.automatic.com/vehicle/vid/",
                    "start_location": {
                        "lat": 32.87336,
                        "lon": -117.22743,
                        "accuracy_m": 10
                    },
                    "start_address": {
                        "name": "123 Fake St, Nowhere, NV 12345",
                        "display_name": "123 Fake St, Nowhere, NV",
                        "street_number": "Unknown",
                        "street_name": "Fake St",
                        "city": "Nowhere",
                        "state": "NV",
                        "country": "US"
                    },
                    "end_location": {
                        "lat": LATITUDE,
                        "lon": LONGITUDE,
                        "accuracy_m": ACCURACY
                    },
                    "end_address": {
                        "name": "321 Fake St, Nowhere, NV 12345",
                        "display_name": "321 Fake St, Nowhere, NV",
                        "street_number": "Unknown",
                        "street_name": "Fake St",
                        "city": "Nowhere",
                        "state": "NV",
                        "country": "US"
                    },
                    "path": "path",
                    "vehicle_events": [],
                    "start_timezone": "America/Denver",
                    "end_timezone": "America/Denver",
                    "idling_time_s": 0,
                    "tags": []
                },
                {
                    "url": "https://api.automatic.com/trip/tid2/",
                    "id": "tid2",
                    "driver": "https://api.automatic.com/user/uid/",
                    "user": "https://api.automatic.com/user/uid/",
                    "started_at": "2016-08-28T18:48:00.727000Z",
                    "ended_at": "2016-08-28T18:55:25.800000Z",
                    "distance_m": 3969.1,
                    "duration_s": 445.1,
                    "vehicle": "https://api.automatic.com/vehicle/vid/",
                    "start_location": {
                        "lat": 32.87336,
                        "lon": -117.22743,
                        "accuracy_m": 11
                    },
                    "start_address": {
                        "name": "123 Fake St, Nowhere, NV, USA",
                        "display_name": "Fake St, Nowhere, NV",
                        "street_number": "123",
                        "street_name": "Fake St",
                        "city": "Nowhere",
                        "state": "NV",
                        "country": "US"
                    },
                    "end_location": {
                        "lat": 32.82336,
                        "lon": -117.23743,
                        "accuracy_m": 10
                    },
                    "end_address": {
                        "name": "321 Fake St, Nowhere, NV, USA",
                        "display_name": "Fake St, Nowhere, NV",
                        "street_number": "Unknown",
                        "street_name": "Fake St",
                        "city": "Nowhere",
                        "state": "NV",
                        "country": "US"
                    },
                    "path": "path",
                    "vehicle_events": [],
                    "start_timezone": "America/Denver",
                    "end_timezone": "America/Denver",
                    "idling_time_s": 0,
                    "tags": []
                }
            ]
        }, 200)
    else:
        _LOGGER.debug('UNKNOWN ROUTE')


class TestAutomatic(unittest.TestCase):
    """Test cases around the automatic device scanner."""

    def see_mock(self, **kwargs):
        """Mock see function."""
        self.assertEqual('vid', kwargs.get('dev_id'))
        self.assertEqual(FUEL_LEVEL,
                         kwargs.get('attributes', {}).get('fuel_level'))
        self.assertEqual((LATITUDE, LONGITUDE), kwargs.get('gps'))
        self.assertEqual(ACCURACY, kwargs.get('gps_accuracy'))

    def setUp(self):
        """Set up test data."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Tear down test data."""

    @patch('requests.get', side_effect=mocked_requests)
    @patch('requests.post', side_effect=mocked_requests)
    def test_invalid_credentials(self, mock_get, mock_post):
        """Test error is raised with invalid credentials."""
        config = {
            'platform': 'automatic',
            'username': INVALID_USERNAME,
            'password': PASSWORD,
            'client_id': CLIENT_ID,
            'secret': CLIENT_SECRET
        }

        self.assertFalse(setup_scanner(self.hass, config, self.see_mock))

    @patch('requests.get', side_effect=mocked_requests)
    @patch('requests.post', side_effect=mocked_requests)
    def test_valid_credentials(self, mock_get, mock_post):
        """Test error is raised with invalid credentials."""
        config = {
            'platform': 'automatic',
            'username': VALID_USERNAME,
            'password': PASSWORD,
            'client_id': CLIENT_ID,
            'secret': CLIENT_SECRET
        }

        self.assertTrue(setup_scanner(self.hass, config, self.see_mock))
