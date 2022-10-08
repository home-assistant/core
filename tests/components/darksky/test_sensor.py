"""The tests for the Dark Sky platform."""
from datetime import timedelta
import re
from unittest.mock import MagicMock, patch

import forecastio
from requests.exceptions import HTTPError

from homeassistant.components.darksky import sensor as darksky
from homeassistant.setup import async_setup_component

from tests.common import load_fixture

VALID_CONFIG_MINIMAL = {
    "sensor": {
        "platform": "darksky",
        "api_key": "foo",
        "forecast": [1, 2],
        "hourly_forecast": [1, 2],
        "monitored_conditions": ["summary", "icon", "temperature_high", "alerts"],
        "scan_interval": timedelta(seconds=120),
    }
}

INVALID_CONFIG_MINIMAL = {
    "sensor": {
        "platform": "darksky",
        "api_key": "foo",
        "forecast": [1, 2],
        "hourly_forecast": [1, 2],
        "monitored_conditions": ["summary", "iocn", "temperature_high"],
        "scan_interval": timedelta(seconds=120),
    }
}

VALID_CONFIG_LANG_DE = {
    "sensor": {
        "platform": "darksky",
        "api_key": "foo",
        "forecast": [1, 2],
        "hourly_forecast": [1, 2],
        "units": "us",
        "language": "de",
        "monitored_conditions": [
            "summary",
            "icon",
            "temperature_high",
            "minutely_summary",
            "hourly_summary",
            "daily_summary",
            "humidity",
            "alerts",
        ],
        "scan_interval": timedelta(seconds=120),
    }
}

INVALID_CONFIG_LANG = {
    "sensor": {
        "platform": "darksky",
        "api_key": "foo",
        "forecast": [1, 2],
        "hourly_forecast": [1, 2],
        "language": "yz",
        "monitored_conditions": ["summary", "icon", "temperature_high"],
        "scan_interval": timedelta(seconds=120),
    }
}

VALID_CONFIG_ALERTS = {
    "sensor": {
        "platform": "darksky",
        "api_key": "foo",
        "forecast": [1, 2],
        "hourly_forecast": [1, 2],
        "monitored_conditions": ["summary", "icon", "temperature_high", "alerts"],
        "scan_interval": timedelta(seconds=120),
    }
}


ENTITIES = []
KEY = "foo"
LAT = 37.8267
LON = -122.423


def load_forecastMock(key, lat, lon, units, lang):  # pylint: disable=invalid-name
    """Mock darksky forecast loading."""
    return ""


def add_entities(new_entities, update_before_add=False):
    """Mock add entities."""
    if update_before_add:
        for entity in new_entities:
            entity.update()

    for entity in new_entities:
        ENTITIES.append(entity)


@patch(
    "homeassistant.components.darksky.sensor.forecastio.load_forecast",
    new=load_forecastMock,
)
async def test_setup_with_config(hass):
    """Test the platform setup with configuration."""
    await async_setup_component(hass, "sensor", VALID_CONFIG_MINIMAL)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.dark_sky_summary")
    assert state is not None


async def test_setup_with_invalid_config(hass):
    """Test the platform setup with invalid configuration."""
    await async_setup_component(hass, "sensor", INVALID_CONFIG_MINIMAL)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.dark_sky_summary")
    assert state is None


@patch(
    "homeassistant.components.darksky.sensor.forecastio.load_forecast",
    new=load_forecastMock,
)
async def test_setup_with_language_config(hass):
    """Test the platform setup with language configuration."""
    await async_setup_component(hass, "sensor", VALID_CONFIG_LANG_DE)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.dark_sky_summary")
    assert state is not None


async def test_setup_with_invalid_language_config(hass):
    """Test the platform setup with language configuration."""
    await async_setup_component(hass, "sensor", INVALID_CONFIG_LANG)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.dark_sky_summary")
    assert state is None


@patch("forecastio.api.get_forecast")
def test_setup_bad_api_key(mock_get_forecast, hass):
    """Test for handling a bad API key."""
    # The Dark Sky API wrapper that we use raises an HTTP error
    # when you try to use a bad (or no) API key.
    url = "https://api.darksky.net/forecast/{}/{},{}?units=auto".format(
        KEY, str(LAT), str(LON)
    )
    msg = f"400 Client Error: Bad Request for url: {url}"
    mock_get_forecast.side_effect = HTTPError(msg)

    response = darksky.setup_platform(hass, VALID_CONFIG_MINIMAL["sensor"], MagicMock())
    assert not response


@patch(
    "homeassistant.components.darksky.sensor.forecastio.load_forecast",
    new=load_forecastMock,
)
async def test_setup_with_alerts_config(hass):
    """Test the platform setup with alert configuration."""
    await async_setup_component(hass, "sensor", VALID_CONFIG_ALERTS)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.dark_sky_alerts")
    assert state.state == "0"


@patch("forecastio.api.get_forecast", wraps=forecastio.api.get_forecast)
async def test_setup(mock_get_forecast, requests_mock, hass):
    """Test for successfully setting up the forecast.io platform."""
    uri = (
        r"https://api.(darksky.net|forecast.io)\/forecast\/(\w+)\/"
        r"(-?\d+\.?\d*),(-?\d+\.?\d*)"
    )
    requests_mock.get(re.compile(uri), text=load_fixture("darksky.json"))

    await async_setup_component(hass, "sensor", VALID_CONFIG_MINIMAL)
    await hass.async_block_till_done()

    assert mock_get_forecast.called
    assert mock_get_forecast.call_count == 1
    assert hass.states.async_entity_ids_count() == 13

    state = hass.states.get("sensor.dark_sky_summary")
    assert state is not None
    assert state.state == "Clear"
    assert state.attributes.get("friendly_name") == "Dark Sky Summary"
    state = hass.states.get("sensor.dark_sky_alerts")
    assert state.state == "2"

    state = hass.states.get("sensor.dark_sky_daytime_high_temperature_1d")
    assert state is not None
    assert state.attributes.get("device_class") == "temperature"
