"""Test Home Assistant location util methods."""
from unittest.mock import Mock, patch

import aiohttp
import pytest

from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.util.location as location_util

from tests.common import load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

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
    return async_get_clientsession(hass)


@pytest.fixture
async def raising_session(event_loop):
    """Return an aioclient session that only fails."""
    return Mock(get=Mock(side_effect=aiohttp.ClientError))


def test_get_distance_to_same_place() -> None:
    """Test getting the distance."""
    meters = location_util.distance(
        COORDINATES_PARIS[0],
        COORDINATES_PARIS[1],
        COORDINATES_PARIS[0],
        COORDINATES_PARIS[1],
    )

    assert meters == 0


def test_get_distance() -> None:
    """Test getting the distance."""
    meters = location_util.distance(
        COORDINATES_PARIS[0],
        COORDINATES_PARIS[1],
        COORDINATES_NEW_YORK[0],
        COORDINATES_NEW_YORK[1],
    )

    assert meters / 1000 - DISTANCE_KM < 0.01


def test_get_kilometers() -> None:
    """Test getting the distance between given coordinates in km."""
    kilometers = location_util.vincenty(COORDINATES_PARIS, COORDINATES_NEW_YORK)
    assert round(kilometers, 2) == DISTANCE_KM


def test_get_miles() -> None:
    """Test getting the distance between given coordinates in miles."""
    miles = location_util.vincenty(COORDINATES_PARIS, COORDINATES_NEW_YORK, miles=True)
    assert round(miles, 2) == DISTANCE_MILES


async def test_detect_location_info_whoami(
    aioclient_mock: AiohttpClientMocker, session
) -> None:
    """Test detect location info using services.home-assistant.io/whoami."""
    aioclient_mock.get(location_util.WHOAMI_URL, text=load_fixture("whoami.json"))

    with patch("homeassistant.util.location.HA_VERSION", "1.0"):
        info = await location_util.async_detect_location_info(session, _test_real=True)

    assert str(aioclient_mock.mock_calls[-1][1]) == location_util.WHOAMI_URL

    assert info is not None
    assert info.ip == "1.2.3.4"
    assert info.country_code == "XX"
    assert info.currency == "XXX"
    assert info.region_code == "00"
    assert info.city == "Gotham"
    assert info.zip_code == "12345"
    assert info.time_zone == "Earth/Gotham"
    assert info.latitude == 12.34567
    assert info.longitude == 12.34567
    assert info.use_metric


async def test_dev_url(aioclient_mock: AiohttpClientMocker, session) -> None:
    """Test usage of dev URL."""
    aioclient_mock.get(location_util.WHOAMI_URL_DEV, text=load_fixture("whoami.json"))
    with patch("homeassistant.util.location.HA_VERSION", "1.0.dev0"):
        info = await location_util.async_detect_location_info(session, _test_real=True)

    assert str(aioclient_mock.mock_calls[-1][1]) == location_util.WHOAMI_URL_DEV

    assert info.currency == "XXX"


async def test_whoami_query_raises(raising_session) -> None:
    """Test whoami query when the request to API fails."""
    info = await location_util._get_whoami(raising_session)
    assert info is None
