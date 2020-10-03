"""The tests for the london_air platform."""
import json

from homeassistant.components.london_air.sensor import CONF_LOCATIONS
from homeassistant.const import HTTP_OK, HTTP_SERVICE_UNAVAILABLE
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import load_fixture

VALID_CONFIG = {"sensor": {"platform": "london_air", CONF_LOCATIONS: ["Merton"]}}


class MockResponse:
    """Class to represent a mocked response."""

    def __init__(self, json_data, status_code):
        """Initialize the mock response class."""
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        """Return the json of the response."""
        return self.json_data


def mocked_requests_get(*args, **kwargs):
    """Mock requests.get invocations."""
    url = str(args[0])

    if "GroupName=London/Json" in url:
        return MockResponse(json.loads(load_fixture("london_air.json")), HTTP_OK)


def mocked_requests_get_failed(*args, **kwargs):
    """Mock requests.get failure."""
    return MockResponse({}, status_code=HTTP_SERVICE_UNAVAILABLE)


async def test_valid_state(hass):
    """Test for operational london_air sensor with proper attributes."""
    with patch("requests.get", mocked_requests_get):
        assert await async_setup_component(hass, "sensor", VALID_CONFIG)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.merton")
        assert state is not None
        assert "Low" == state.state
        assert "mdi:cloud-outline" == state.attributes["icon"]
        assert "2017-08-03 03:00:00" == state.attributes["updated"]
        assert 2 == state.attributes["sites"]
        assert "Merton" == state.attributes["friendly_name"]

        sites = state.attributes["data"]
        assert sites is not None
        assert 2 == len(sites)
        assert "ME2" == sites[0]["site_code"]
        assert "Roadside" == sites[0]["site_type"]
        assert "Merton Road" == sites[0]["site_name"]
        assert "Low" == sites[0]["pollutants_status"]

        pollutants = sites[0]["pollutants"]
        assert pollutants is not None
        assert 1 == len(pollutants)
        assert "PM10" == pollutants[0]["code"]
        assert "Low" == pollutants[0]["quality"]
        assert 2 == int(pollutants[0]["index"])
        assert "PM10 is Low" == pollutants[0]["summary"]


async def test_api_failure(hass):
    """Test for failure in the API."""
    with patch("requests.get", mocked_requests_get_failed):
        assert await async_setup_component(hass, "sensor", VALID_CONFIG)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.merton")
        assert state is not None
        assert None is state.attributes["updated"]
        assert 0 == state.attributes["sites"]
