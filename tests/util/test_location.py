"""Test Home Assistant location util methods."""
import aiohttp
from asynctest import Mock, patch
import pytest

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


@pytest.fixture
async def session(hass):
    """Return aioclient session."""
    return hass.helpers.aiohttp_client.async_get_clientsession()


@pytest.fixture
async def raising_session(loop):
    """Return an aioclient session that only fails."""
    return Mock(get=Mock(side_effect=aiohttp.ClientError))


def test_get_distance_to_same_place():
    """Test getting the distance."""
    meters = location_util.distance(
        COORDINATES_PARIS[0],
        COORDINATES_PARIS[1],
        COORDINATES_PARIS[0],
        COORDINATES_PARIS[1],
    )

    assert meters == 0


def test_get_distance():
    """Test getting the distance."""
    meters = location_util.distance(
        COORDINATES_PARIS[0],
        COORDINATES_PARIS[1],
        COORDINATES_NEW_YORK[0],
        COORDINATES_NEW_YORK[1],
    )

    assert meters / 1000 - DISTANCE_KM < 0.01


def test_get_kilometers():
    """Test getting the distance between given coordinates in km."""
    kilometers = location_util.vincenty(COORDINATES_PARIS, COORDINATES_NEW_YORK)
    assert round(kilometers, 2) == DISTANCE_KM


def test_get_miles():
    """Test getting the distance between given coordinates in miles."""
    miles = location_util.vincenty(COORDINATES_PARIS, COORDINATES_NEW_YORK, miles=True)
    assert round(miles, 2) == DISTANCE_MILES


async def test_detect_location_info_ipapi(aioclient_mock, session):
    """Test detect location info using ipapi.co."""
    aioclient_mock.get(location_util.IPAPI, text=load_fixture("ipapi.co.json"))

    info = await location_util.async_detect_location_info(session, _test_real=True)

    assert info is not None
    assert info.ip == "1.2.3.4"
    assert info.country_code == "CH"
    assert info.country_name == "Switzerland"
    assert info.region_code == "BE"
    assert info.region_name == "Bern"
    assert info.city == "Bern"
    assert info.zip_code == "3000"
    assert info.time_zone == "Europe/Zurich"
    assert info.latitude == 46.9480278
    assert info.longitude == 7.4490812
    assert info.use_metric


async def test_detect_location_info_ipapi_exhaust(aioclient_mock, session):
    """Test detect location info using ipapi.co."""
    aioclient_mock.get(location_util.IPAPI, json={"latitude": "Sign up to access"})
    aioclient_mock.get(location_util.IP_API, text=load_fixture("ip-api.com.json"))

    info = await location_util.async_detect_location_info(session, _test_real=True)

    assert info is not None
    # ip_api result because ipapi got skipped
    assert info.country_code == "US"
    assert len(aioclient_mock.mock_calls) == 2


async def test_detect_location_info_ip_api(aioclient_mock, session):
    """Test detect location info using ip-api.com."""
    aioclient_mock.get(location_util.IP_API, text=load_fixture("ip-api.com.json"))

    with patch("homeassistant.util.location._get_ipapi", return_value=None):
        info = await location_util.async_detect_location_info(session, _test_real=True)

    assert info is not None
    assert info.ip == "1.2.3.4"
    assert info.country_code == "US"
    assert info.country_name == "United States"
    assert info.region_code == "CA"
    assert info.region_name == "California"
    assert info.city == "San Diego"
    assert info.zip_code == "92122"
    assert info.time_zone == "America/Los_Angeles"
    assert info.latitude == 32.8594
    assert info.longitude == -117.2073
    assert not info.use_metric


async def test_detect_location_info_both_queries_fail(session):
    """Ensure we return None if both queries fail."""
    with patch("homeassistant.util.location._get_ipapi", return_value=None), patch(
        "homeassistant.util.location._get_ip_api", return_value=None
    ):
        info = await location_util.async_detect_location_info(session, _test_real=True)
    assert info is None


async def test_freegeoip_query_raises(raising_session):
    """Test ipapi.co query when the request to API fails."""
    info = await location_util._get_ipapi(raising_session)
    assert info is None


async def test_ip_api_query_raises(raising_session):
    """Test ip api query when the request to API fails."""
    info = await location_util._get_ip_api(raising_session)
    assert info is None
