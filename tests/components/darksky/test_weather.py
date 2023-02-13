"""The tests for the Dark Sky weather component."""
import re
from unittest.mock import patch

import forecastio
from requests.exceptions import ConnectionError as ConnectError
import requests_mock

from homeassistant.components import weather
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import load_fixture


async def test_setup(hass: HomeAssistant, requests_mock: requests_mock.Mocker) -> None:
    """Test for successfully setting up the forecast.io platform."""
    with patch(
        "forecastio.api.get_forecast", wraps=forecastio.api.get_forecast
    ) as mock_get_forecast:
        requests_mock.get(
            re.compile(
                r"https://api.(darksky.net|forecast.io)\/forecast\/(\w+)\/"
                r"(-?\d+\.?\d*),(-?\d+\.?\d*)"
            ),
            text=load_fixture("darksky.json"),
        )

        assert await async_setup_component(
            hass,
            weather.DOMAIN,
            {"weather": {"name": "test", "platform": "darksky", "api_key": "foo"}},
        )
        await hass.async_block_till_done()

        assert mock_get_forecast.call_count == 1
        state = hass.states.get("weather.test")
        assert state.state == "sunny"


async def test_failed_setup(hass: HomeAssistant) -> None:
    """Test to ensure that a network error does not break component state."""
    with patch("forecastio.load_forecast", side_effect=ConnectError()):
        assert await async_setup_component(
            hass,
            weather.DOMAIN,
            {"weather": {"name": "test", "platform": "darksky", "api_key": "foo"}},
        )
        await hass.async_block_till_done()

        state = hass.states.get("weather.test")
        assert state.state == "unavailable"
