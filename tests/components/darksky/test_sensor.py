"""The tests for the Dark Sky platform."""
from datetime import timedelta
import re
from unittest.mock import patch

import forecastio
from requests.exceptions import ConnectionError as ConnectError
import requests_mock

from homeassistant.core import HomeAssistant
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


async def test_setup_with_config(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test the platform setup with configuration."""
    with patch("homeassistant.components.darksky.sensor.forecastio.load_forecast"):
        assert await async_setup_component(hass, "sensor", VALID_CONFIG_MINIMAL)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.dark_sky_summary")
        assert state is not None


async def test_setup_with_invalid_config(hass: HomeAssistant) -> None:
    """Test the platform setup with invalid configuration."""
    assert await async_setup_component(hass, "sensor", INVALID_CONFIG_MINIMAL)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.dark_sky_summary")
    assert state is None


async def test_setup_with_language_config(hass: HomeAssistant) -> None:
    """Test the platform setup with language configuration."""
    with patch("homeassistant.components.darksky.sensor.forecastio.load_forecast"):
        assert await async_setup_component(hass, "sensor", VALID_CONFIG_LANG_DE)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.dark_sky_summary")
        assert state is not None


async def test_setup_with_invalid_language_config(hass: HomeAssistant) -> None:
    """Test the platform setup with language configuration."""
    assert await async_setup_component(hass, "sensor", INVALID_CONFIG_LANG)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.dark_sky_summary")
    assert state is None


async def test_setup_bad_api_key(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test for handling a bad API key."""
    # The Dark Sky API wrapper that we use raises an HTTP error
    # when you try to use a bad (or no) API key.
    url = "https://api.darksky.net/forecast/{}/{},{}?units=auto".format(
        "foo", str(hass.config.latitude), str(hass.config.longitude)
    )
    msg = f"400 Client Error: Bad Request for url: {url}"
    requests_mock.get(url, text=msg, status_code=400)

    assert await async_setup_component(
        hass, "sensor", {"sensor": {"platform": "darksky", "api_key": "foo"}}
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.dark_sky_summary") is None


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test setting up with a connection error."""
    with patch(
        "homeassistant.components.darksky.sensor.forecastio.load_forecast",
        side_effect=ConnectError(),
    ):
        await async_setup_component(hass, "sensor", VALID_CONFIG_MINIMAL)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.dark_sky_summary")
        assert state is None


async def test_setup(hass: HomeAssistant, requests_mock: requests_mock.Mocker) -> None:
    """Test for successfully setting up the forecast.io platform."""
    with patch(
        "forecastio.api.get_forecast", wraps=forecastio.api.get_forecast
    ) as mock_get_forecast:
        uri = (
            r"https://api.(darksky.net|forecast.io)\/forecast\/(\w+)\/"
            r"(-?\d+\.?\d*),(-?\d+\.?\d*)"
        )
        requests_mock.get(re.compile(uri), text=load_fixture("darksky.json"))

        assert await async_setup_component(hass, "sensor", VALID_CONFIG_MINIMAL)
        await hass.async_block_till_done()

        assert mock_get_forecast.call_count == 1
        assert len(hass.states.async_entity_ids()) == 13

        state = hass.states.get("sensor.dark_sky_summary")
        assert state is not None
        assert state.state == "Clear"
        assert state.attributes.get("friendly_name") == "Dark Sky Summary"
        state = hass.states.get("sensor.dark_sky_alerts")
        assert state.state == "2"

        state = hass.states.get("sensor.dark_sky_daytime_high_temperature_1d")
        assert state is not None
        assert state.attributes.get("device_class") == "temperature"
