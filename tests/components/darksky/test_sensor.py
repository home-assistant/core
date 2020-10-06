"""The tests for the Dark Sky platform."""
from requests.exceptions import HTTPError

from homeassistant.components.darksky import sensor as darksky
from homeassistant.setup import async_setup_component

from .const import (
    INVALID_CONFIG_LANG,
    INVALID_CONFIG_MINIMAL,
    VALID_CONFIG_ALERTS,
    VALID_CONFIG_LANG_DE,
    VALID_CONFIG_MINIMAL,
)

from tests.async_mock import MagicMock, patch

KEY = "foo"
LAT = 37.8267
LON = -122.423


def load_forecastMock(key, lat, lon, units, lang):  # pylint: disable=invalid-name
    """Mock darksky forecast loading."""
    return ""


async def test_setup_with_config(hass):
    """Test the platform setup with configuration."""
    with patch(
        "homeassistant.components.darksky.sensor.forecastio.load_forecast",
        new=load_forecastMock,
    ):
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


async def test_setup_with_language_config(hass):
    """Test the platform setup with language configuration."""
    with patch(
        "homeassistant.components.darksky.sensor.forecastio.load_forecast",
        new=load_forecastMock,
    ):
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


async def test_setup_bad_api_key(hass):
    """Test for handling a bad API key."""
    # The Dark Sky API wrapper that we use raises an HTTP error
    # when you try to use a bad (or no) API key.
    url = "https://api.darksky.net/forecast/{}/{},{}?units=auto".format(
        KEY, str(LAT), str(LON)
    )
    msg = f"400 Client Error: Bad Request for url: {url}"
    with patch("forecastio.api.get_forecast") as mock_get_forecast:
        mock_get_forecast.side_effect = HTTPError(msg)

    response = darksky.setup_platform(hass, VALID_CONFIG_MINIMAL["sensor"], MagicMock())
    assert not response


async def test_setup_with_alerts_config(hass):
    """Test the platform setup with alert configuration."""
    with patch(
        "homeassistant.components.darksky.sensor.forecastio.load_forecast",
        new=load_forecastMock,
    ):
        await async_setup_component(hass, "sensor", VALID_CONFIG_ALERTS)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.dark_sky_alerts")
    assert state.state == "0"


# def test_setup(hass):
#     """Test for successfully setting up the forecast.io platform."""
#     uri = (
#         r"https://api.(darksky.net|forecast.io)\/forecast\/(\w+)\/"
#         r"(-?\d+\.?\d*),(-?\d+\.?\d*)"
#     )
#     mock_req = patch("forecastio.api.get_forecast", wraps=forecastio.api.get_forecast)
#     mock_req.get(re.compile(uri), text=load_fixture("darksky.json"))

#     assert async_setup_component(hass, "sensor", VALID_CONFIG_MINIMAL)
#     hass.block_till_done()

#     with requests_mock.Mocker() as mock_get_forecast:
#         assert mock_get_forecast.called
#         assert mock_get_forecast.call_count == 1
#     assert len(hass.states.entity_ids()) == 13

#     state = hass.states.get("sensor.dark_sky_summary")
#     assert state is not None
#     assert state.state == "Clear"
#     assert state.attributes.get("friendly_name") == "Dark Sky Summary"
#     state = hass.states.get("sensor.dark_sky_alerts")
#     assert state.state == "2"

#     state = hass.states.get("sensor.dark_sky_daytime_high_temperature_1d")
#     assert state is not None
#     assert state.attributes.get("device_class") == "temperature"
