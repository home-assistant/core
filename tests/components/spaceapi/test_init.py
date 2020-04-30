"""The tests for the Home Assistant SpaceAPI component."""
# pylint: disable=protected-access
from unittest.mock import patch

import pytest

from homeassistant.components.spaceapi import DOMAIN, SPACEAPI_VERSION, URL_API_SPACEAPI
from homeassistant.const import TEMP_CELSIUS, UNIT_PERCENTAGE
from homeassistant.setup import async_setup_component

from tests.common import mock_coro

CONFIG = {
    DOMAIN: {
        "space": "Home",
        "logo": "https://home-assistant.io/logo.png",
        "url": "https://home-assistant.io",
        "location": {"address": "In your Home"},
        "contact": {"email": "hello@home-assistant.io"},
        "issue_report_channels": ["email"],
        "state": {
            "entity_id": "test.test_door",
            "icon_open": "https://home-assistant.io/open.png",
            "icon_closed": "https://home-assistant.io/close.png",
        },
        "sensors": {
            "temperature": ["test.temp1", "test.temp2"],
            "humidity": ["test.hum1"],
        },
        "spacefed": {"spacenet": True, "spacesaml": False, "spacephone": True},
        "cam": ["https://home-assistant.io/cam1", "https://home-assistant.io/cam2"],
        "stream": {
            "m4": "https://home-assistant.io/m4",
            "mjpeg": "https://home-assistant.io/mjpeg",
            "ustream": "https://home-assistant.io/ustream",
        },
        "feeds": {
            "blog": {"url": "https://home-assistant.io/blog"},
            "wiki": {"type": "mediawiki", "url": "https://home-assistant.io/wiki"},
            "calendar": {"type": "ical", "url": "https://home-assistant.io/calendar"},
            "flicker": {"url": "https://www.flickr.com/photos/home-assistant"},
        },
        "cache": {"schedule": "m.02"},
        "projects": [
            "https://home-assistant.io/projects/1",
            "https://home-assistant.io/projects/2",
            "https://home-assistant.io/projects/3",
        ],
        "radio_show": [
            {
                "name": "Radioshow",
                "url": "https://home-assistant.io/radio",
                "type": "ogg",
                "start": "2019-09-02T10:00Z",
                "end": "2019-09-02T12:00Z",
            }
        ],
    }
}

SENSOR_OUTPUT = {
    "temperature": [
        {"location": "Home", "name": "temp1", "unit": TEMP_CELSIUS, "value": "25"},
        {"location": "Home", "name": "temp2", "unit": TEMP_CELSIUS, "value": "23"},
    ],
    "humidity": [
        {"location": "Home", "name": "hum1", "unit": UNIT_PERCENTAGE, "value": "88"}
    ],
}


@pytest.fixture
def mock_client(hass, hass_client):
    """Start the Home Assistant HTTP component."""
    with patch("homeassistant.components.spaceapi", return_value=mock_coro(True)):
        hass.loop.run_until_complete(async_setup_component(hass, "spaceapi", CONFIG))

    hass.states.async_set(
        "test.temp1", 25, attributes={"unit_of_measurement": TEMP_CELSIUS}
    )
    hass.states.async_set(
        "test.temp2", 23, attributes={"unit_of_measurement": TEMP_CELSIUS}
    )
    hass.states.async_set(
        "test.hum1", 88, attributes={"unit_of_measurement": UNIT_PERCENTAGE}
    )

    return hass.loop.run_until_complete(hass_client())


async def test_spaceapi_get(hass, mock_client):
    """Test response after start-up Home Assistant."""
    resp = await mock_client.get(URL_API_SPACEAPI)
    assert resp.status == 200

    data = await resp.json()

    assert data["api"] == SPACEAPI_VERSION
    assert data["space"] == "Home"
    assert data["contact"]["email"] == "hello@home-assistant.io"
    assert data["location"]["address"] == "In your Home"
    assert data["location"]["lat"] == 32.87336
    assert data["location"]["lon"] == -117.22743
    assert data["state"]["open"] == "null"
    assert data["state"]["icon"]["open"] == "https://home-assistant.io/open.png"
    assert data["state"]["icon"]["close"] == "https://home-assistant.io/close.png"
    assert data["spacefed"]["spacenet"] == bool(1)
    assert data["spacefed"]["spacesaml"] == bool(0)
    assert data["spacefed"]["spacephone"] == bool(1)
    assert data["cam"][0] == "https://home-assistant.io/cam1"
    assert data["cam"][1] == "https://home-assistant.io/cam2"
    assert data["stream"]["m4"] == "https://home-assistant.io/m4"
    assert data["stream"]["mjpeg"] == "https://home-assistant.io/mjpeg"
    assert data["stream"]["ustream"] == "https://home-assistant.io/ustream"
    assert data["feeds"]["blog"]["url"] == "https://home-assistant.io/blog"
    assert data["feeds"]["wiki"]["type"] == "mediawiki"
    assert data["feeds"]["wiki"]["url"] == "https://home-assistant.io/wiki"
    assert data["feeds"]["calendar"]["type"] == "ical"
    assert data["feeds"]["calendar"]["url"] == "https://home-assistant.io/calendar"
    assert (
        data["feeds"]["flicker"]["url"]
        == "https://www.flickr.com/photos/home-assistant"
    )
    assert data["cache"]["schedule"] == "m.02"
    assert data["projects"][0] == "https://home-assistant.io/projects/1"
    assert data["projects"][1] == "https://home-assistant.io/projects/2"
    assert data["projects"][2] == "https://home-assistant.io/projects/3"
    assert data["radio_show"][0]["name"] == "Radioshow"
    assert data["radio_show"][0]["url"] == "https://home-assistant.io/radio"
    assert data["radio_show"][0]["type"] == "ogg"
    assert data["radio_show"][0]["start"] == "2019-09-02T10:00Z"
    assert data["radio_show"][0]["end"] == "2019-09-02T12:00Z"


async def test_spaceapi_state_get(hass, mock_client):
    """Test response if the state entity was set."""
    hass.states.async_set("test.test_door", True)

    resp = await mock_client.get(URL_API_SPACEAPI)
    assert resp.status == 200

    data = await resp.json()
    assert data["state"]["open"] == bool(1)


async def test_spaceapi_sensors_get(hass, mock_client):
    """Test the response for the sensors."""
    resp = await mock_client.get(URL_API_SPACEAPI)
    assert resp.status == 200

    data = await resp.json()
    assert data["sensors"] == SENSOR_OUTPUT
