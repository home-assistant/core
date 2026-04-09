"""The tests for the Home Assistant SpaceAPI component."""

from http import HTTPStatus

from aiohttp.test_utils import TestClient
import pytest

from homeassistant.components.spaceapi import (
    ATTR_SENSOR_LOCATION,
    SPACEAPI_COMPATIBILITY,
    URL_API_SPACEAPI,
)
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

SENSOR_OUTPUT = {
    "temperature": [
        {
            "location": "Home",
            "name": "temp1",
            "unit": UnitOfTemperature.CELSIUS,
            "value": 25.0,
        },
        {
            "location": "outside",
            "name": "temp2",
            "unit": UnitOfTemperature.CELSIUS,
            "value": 23.0,
        },
        {
            "location": "Home",
            "name": "temp3",
            "unit": UnitOfTemperature.CELSIUS,
            "value": None,
        },
    ],
    "humidity": [
        {"location": "Home", "name": "hum1", "unit": PERCENTAGE, "value": 88.0}
    ],
}


@pytest.fixture
async def mock_client(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> TestClient:
    """Start the Home Assistant HTTP component."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(
        "test.temp1",
        25,
        attributes={ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    hass.states.async_set(
        "test.temp2",
        23,
        attributes={
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            ATTR_SENSOR_LOCATION: "outside",
        },
    )
    hass.states.async_set(
        "test.temp3",
        "foo",
        attributes={ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    hass.states.async_set(
        "test.temp3",
        "foo",
        attributes={ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    hass.states.async_set(
        "test.hum1", 88, attributes={ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE}
    )

    return await hass_client()


async def test_spaceapi_get(hass: HomeAssistant, mock_client: TestClient) -> None:
    """Test response after start-up Home Assistant."""
    resp = await mock_client.get(URL_API_SPACEAPI)
    assert resp.status == HTTPStatus.OK

    data = await resp.json()

    assert data["api_compatibility"] == SPACEAPI_COMPATIBILITY
    assert data["space"] == "Home"
    assert data["contact"]["email"] == "hello@home-assistant.io"
    assert data["location"]["lat"] == 32.87336
    assert data["location"]["lon"] == -117.22743
    assert data["state"]["open"] is False
    assert data["state"]["icon"]["open"] == "https://home-assistant.io/open.png"
    assert data["state"]["icon"]["closed"] == "https://home-assistant.io/close.png"
    assert data["spacefed"]["spacenet"] is True
    assert data["spacefed"]["spacesaml"] is False
    assert "spacephone" not in data["spacefed"]
    assert data["cam"][0] == "https://home-assistant.io/cam1"
    assert data["cam"][1] == "https://home-assistant.io/cam2"
    assert "stream" not in data
    assert data["feeds"]["blog"]["url"] == "https://home-assistant.io/blog"
    assert data["feeds"]["wiki"]["type"] == "mediawiki"
    assert data["feeds"]["wiki"]["url"] == "https://home-assistant.io/wiki"
    assert data["feeds"]["calendar"]["type"] == "ical"
    assert data["feeds"]["calendar"]["url"] == "https://home-assistant.io/calendar"
    assert (
        data["feeds"]["flicker"]["url"]
        == "https://www.flickr.com/photos/home-assistant"
    )
    assert "cache" not in data
    assert data["projects"][0] == "https://home-assistant.io/projects/1"
    assert data["projects"][1] == "https://home-assistant.io/projects/2"
    assert data["projects"][2] == "https://home-assistant.io/projects/3"
    assert "radio_show" not in data
    assert "issue_report_channels" not in data


async def test_spaceapi_state_get(hass: HomeAssistant, mock_client: TestClient) -> None:
    """Test response if the state entity was set."""
    hass.states.async_set("test.test_door", True)

    resp = await mock_client.get(URL_API_SPACEAPI)
    assert resp.status == HTTPStatus.OK

    data = await resp.json()
    assert data["state"]["open"] is True


async def test_spaceapi_sensors_get(
    hass: HomeAssistant, mock_client: TestClient
) -> None:
    """Test the response for the sensors."""
    resp = await mock_client.get(URL_API_SPACEAPI)
    assert resp.status == HTTPStatus.OK

    data = await resp.json()
    assert data["sensors"] == SENSOR_OUTPUT


async def test_spaceapi_no_auth_required(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test SpaceAPI is accessible without authentication."""
    assert await async_setup_component(hass, "spaceapi", CONFIG)

    hass.states.async_set("test.test_door", "on")

    client = await hass_client_no_auth()
    resp = await client.get(URL_API_SPACEAPI)
    assert resp.status == HTTPStatus.OK

    data = await resp.json()
    assert data["space"] == "Home"


async def test_spaceapi_cors_headers(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test CORS headers are present on SpaceAPI responses."""
    assert await async_setup_component(hass, "spaceapi", CONFIG)

    hass.states.async_set("test.test_door", "on")

    client = await hass_client_no_auth()
    resp = await client.options(
        URL_API_SPACEAPI,
        headers={
            "origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers["Access-Control-Allow-Origin"] == "http://example.com"
    assert "GET" in resp.headers["Access-Control-Allow-Methods"]
