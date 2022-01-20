"""The tests for the london_air platform."""
from http import HTTPStatus

from homeassistant.components.london_air.sensor import CONF_LOCATIONS, URL
from homeassistant.setup import async_setup_component

from tests.common import load_fixture

VALID_CONFIG = {"sensor": {"platform": "london_air", CONF_LOCATIONS: ["Merton"]}}


async def test_valid_state(hass, requests_mock):
    """Test for operational london_air sensor with proper attributes."""
    requests_mock.get(
        URL, text=load_fixture("london_air.json"), status_code=HTTPStatus.OK
    )
    assert await async_setup_component(hass, "sensor", VALID_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.merton")
    assert state is not None
    assert state.state == "Low"
    assert state.attributes["icon"] == "mdi:cloud-outline"
    assert state.attributes["updated"] == "2017-08-03 03:00:00"
    assert state.attributes["sites"] == 2
    assert state.attributes["friendly_name"] == "Merton"

    sites = state.attributes["data"]
    assert sites is not None
    assert len(sites) == 2
    assert sites[0]["site_code"] == "ME2"
    assert sites[0]["site_type"] == "Roadside"
    assert sites[0]["site_name"] == "Merton Road"
    assert sites[0]["pollutants_status"] == "Low"

    pollutants = sites[0]["pollutants"]
    assert pollutants is not None
    assert len(pollutants) == 1
    assert pollutants[0]["code"] == "PM10"
    assert pollutants[0]["quality"] == "Low"
    assert int(pollutants[0]["index"]) == 2
    assert pollutants[0]["summary"] == "PM10 is Low"


async def test_api_failure(hass, requests_mock):
    """Test for failure in the API."""
    requests_mock.get(URL, status_code=HTTPStatus.SERVICE_UNAVAILABLE)
    assert await async_setup_component(hass, "sensor", VALID_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.merton")
    assert state is not None
    assert state.attributes["updated"] is None
    assert state.attributes["sites"] == 0
