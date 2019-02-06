"""Test Home Assistant location util methods."""
from unittest import TestCase
from unittest.mock import patch

import requests
import requests_mock

import homeassistant.util.location as location_util

from tests.common import load_fixture

# Paris
COORDINATES_PARIS = (48.864716, 2.349014)
# New York
COORDINATES_NEW_YORK = (40.730610, -73.935242)

# Results for the assertion (vincenty algorithm):
#      Distance [km]   Distance [miles]
# [0]  5846.39         3632.78
# [1]  5851            3635
#
# [0]: http://boulter.com/gps/distance/
# [1]: https://www.wolframalpha.com/input/?i=from+paris+to+new+york
DISTANCE_KM = 5846.39
DISTANCE_MILES = 3632.78


class TestLocationUtil(TestCase):
    """Test util location methods."""

    def test_get_distance_to_same_place(self):
        """Test getting the distance."""
        meters = location_util.distance(
            COORDINATES_PARIS[0], COORDINATES_PARIS[1],
            COORDINATES_PARIS[0], COORDINATES_PARIS[1])

        assert meters == 0

    def test_get_distance(self):
        """Test getting the distance."""
        meters = location_util.distance(
            COORDINATES_PARIS[0], COORDINATES_PARIS[1],
            COORDINATES_NEW_YORK[0], COORDINATES_NEW_YORK[1])

        assert meters/1000 - DISTANCE_KM < 0.01

    def test_get_kilometers(self):
        """Test getting the distance between given coordinates in km."""
        kilometers = location_util.vincenty(
            COORDINATES_PARIS, COORDINATES_NEW_YORK)
        assert round(kilometers, 2) == DISTANCE_KM

    def test_get_miles(self):
        """Test getting the distance between given coordinates in miles."""
        miles = location_util.vincenty(
            COORDINATES_PARIS, COORDINATES_NEW_YORK, miles=True)
        assert round(miles, 2) == DISTANCE_MILES

    @requests_mock.Mocker()
    def test_detect_location_info_ipapi(self, m):
        """Test detect location info using ipapi.co."""
        m.get(
            location_util.IPAPI, text=load_fixture('ipapi.co.json'))

        info = location_util.detect_location_info(_test_real=True)

        assert info is not None
        assert info.ip == '1.2.3.4'
        assert info.country_code == 'CH'
        assert info.country_name == 'Switzerland'
        assert info.region_code == 'BE'
        assert info.region_name == 'Bern'
        assert info.city == 'Bern'
        assert info.zip_code == '3000'
        assert info.time_zone == 'Europe/Zurich'
        assert info.latitude == 46.9480278
        assert info.longitude == 7.4490812
        assert info.use_metric

    @requests_mock.Mocker()
    @patch('homeassistant.util.location._get_ipapi', return_value=None)
    def test_detect_location_info_ip_api(self, mock_req, mock_ipapi):
        """Test detect location info using ip-api.com."""
        mock_req.get(
            location_util.IP_API, text=load_fixture('ip-api.com.json'))

        info = location_util.detect_location_info(_test_real=True)

        assert info is not None
        assert info.ip == '1.2.3.4'
        assert info.country_code == 'US'
        assert info.country_name == 'United States'
        assert info.region_code == 'CA'
        assert info.region_name == 'California'
        assert info.city == 'San Diego'
        assert info.zip_code == '92122'
        assert info.time_zone == 'America/Los_Angeles'
        assert info.latitude == 32.8594
        assert info.longitude == -117.2073
        assert not info.use_metric

    @patch('homeassistant.util.location.elevation', return_value=0)
    @patch('homeassistant.util.location._get_ipapi', return_value=None)
    @patch('homeassistant.util.location._get_ip_api', return_value=None)
    def test_detect_location_info_both_queries_fail(
            self, mock_ipapi, mock_ip_api, mock_elevation):
        """Ensure we return None if both queries fail."""
        info = location_util.detect_location_info(_test_real=True)
        assert info is None

    @patch('homeassistant.util.location.requests.get',
           side_effect=requests.RequestException)
    def test_freegeoip_query_raises(self, mock_get):
        """Test ipapi.co query when the request to API fails."""
        info = location_util._get_ipapi()
        assert info is None

    @patch('homeassistant.util.location.requests.get',
           side_effect=requests.RequestException)
    def test_ip_api_query_raises(self, mock_get):
        """Test ip api query when the request to API fails."""
        info = location_util._get_ip_api()
        assert info is None

    @patch('homeassistant.util.location.requests.get',
           side_effect=requests.RequestException)
    def test_elevation_query_raises(self, mock_get):
        """Test elevation when the request to API fails."""
        elevation = location_util.elevation(10, 10, _test_real=True)
        assert elevation == 0

    @requests_mock.Mocker()
    def test_elevation_query_fails(self, mock_req):
        """Test elevation when the request to API fails."""
        mock_req.get(location_util.ELEVATION_URL, text='{}', status_code=401)
        elevation = location_util.elevation(10, 10, _test_real=True)
        assert elevation == 0

    @requests_mock.Mocker()
    def test_elevation_query_nonjson(self, mock_req):
        """Test if elevation API returns a non JSON value."""
        mock_req.get(location_util.ELEVATION_URL, text='{ I am not JSON }')
        elevation = location_util.elevation(10, 10, _test_real=True)
        assert elevation == 0
