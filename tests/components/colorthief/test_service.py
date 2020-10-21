"""Tests for colorthief component service calls."""
import base64

import aiohttp
import pytest

from homeassistant.components.colorthief import (
    ATTR_FILE_PATH,
    ATTR_LIGHT_ENTITY_ID,
    ATTR_URL,
    DOMAIN,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component

from tests.async_mock import Mock, mock_open, patch
from tests.common import load_fixture

LIGHT_ENTITY = "light.kitchen_lights"
CLOSE_THRESHOLD = 5


def _close_enough(actual_rgb, testing_rgb):
    """Validate the given RGB value is in acceptable tolerance."""
    actual_red, actual_green, actual_blue = actual_rgb
    testing_red, testing_green, testing_blue = testing_rgb

    r_diff = abs(actual_red - testing_red)
    g_diff = abs(actual_green - testing_green)
    b_diff = abs(actual_blue - testing_blue)

    return (
        r_diff <= CLOSE_THRESHOLD
        and g_diff <= CLOSE_THRESHOLD
        and b_diff <= CLOSE_THRESHOLD
    )


@pytest.fixture(autouse=True)
async def setup_light(hass):
    """Configure our light component to work against for testing."""
    assert await async_setup_component(
        hass, LIGHT_DOMAIN, {LIGHT_DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(LIGHT_ENTITY)
    assert state

    # Validate starting values
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 180
    assert state.attributes.get(ATTR_RGB_COLOR) == (255, 63, 111)

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: LIGHT_ENTITY}, blocking=True
    )
    await hass.async_block_till_done()

    state = hass.states.get(LIGHT_ENTITY)

    assert state
    assert state.state == STATE_OFF


async def test_url_success(hass, aioclient_mock):
    """Test that a successful image GET translate to light RGB."""
    service_data = {
        ATTR_URL: "http://example.com/images/logo.png",
        ATTR_LIGHT_ENTITY_ID: LIGHT_ENTITY,
        ATTR_BRIGHTNESS_PCT: 50,
    }

    # Mock the HTTP Response with a base64 encoded 1x1 pixel
    aioclient_mock.get(
        url=service_data["url"],
        content=base64.b64decode(load_fixture("colorthief_url.txt")),
    )

    await _async_load_colorthief_url(hass, service_data)

    state = hass.states.get(LIGHT_ENTITY)
    assert state

    # Ensure we turned it on
    assert state.state == STATE_ON

    # Brightness has changed, optional service call field
    assert state.attributes[ATTR_BRIGHTNESS] == 128

    # RGB has changed though
    assert state.attributes.get(ATTR_RGB_COLOR) != (255, 63, 111)

    # Ensure the RGB values are correct
    # TODO: Why does the demo light not set / report the rgb_color correctly!
    # assert _close_enough(state.attributes[ATTR_RGB_COLOR], (50, 100, 150))


async def _async_load_colorthief_url(hass, service_data):
    # Load our ColorThief component
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Validate pre service call
    state = hass.states.get(LIGHT_ENTITY)
    assert state
    assert state.state == STATE_OFF

    # Call the URL specific service, our above mock should return the base64 decoded fixture 1x1 pixel
    await hass.services.async_call(
        DOMAIN, "predominant_color_url", service_data, blocking=True
    )

    await hass.async_block_till_done()


async def test_url_exception(hass, aioclient_mock):
    """Test that a HTTPError fails to turn light on."""
    service_data = {
        ATTR_URL: "http://example.com/images/logo.png",
        ATTR_LIGHT_ENTITY_ID: LIGHT_ENTITY,
    }

    # Mock the HTTP Response with a base64 encoded 1x1 pixel
    aioclient_mock.get(url=service_data["url"], exc=aiohttp.ClientError)

    await _async_load_colorthief_url(hass, service_data)

    # Light has not been modified due to failure
    state = hass.states.get(LIGHT_ENTITY)
    assert state
    assert state.state == STATE_OFF


async def test_url_error(hass, aioclient_mock):
    """Test that a HTTP Error (non 200) doesn't turn light on."""
    service_data = {
        ATTR_URL: "http://example.com/images/logo.png",
        ATTR_LIGHT_ENTITY_ID: LIGHT_ENTITY,
    }

    # Mock the HTTP Response with a base64 encoded 1x1 pixel
    aioclient_mock.get(url=service_data["url"], status=400)

    await _async_load_colorthief_url(hass, service_data)

    # Light has not been modified due to failure
    state = hass.states.get(LIGHT_ENTITY)
    assert state
    assert state.state == STATE_OFF


@patch("os.path.isfile", Mock(return_value=True))
@patch("os.access", Mock(return_value=True))
@patch(
    "builtins.open",
    mock_open(read_data=base64.b64decode(load_fixture("colorthief_file.txt"))),
    create=True,
)
async def test_file(hass):
    """Test that the file only service reads a file and translates to light RGB."""
    service_data = {
        ATTR_FILE_PATH: "/path/to/an/image.png",
        ATTR_LIGHT_ENTITY_ID: LIGHT_ENTITY,
        ATTR_BRIGHTNESS_PCT: 100,
    }

    await async_setup_component(hass, DOMAIN, {})

    # Verify pre service check
    state = hass.states.get(LIGHT_ENTITY)
    assert state
    assert state.state == STATE_OFF

    await hass.services.async_call(DOMAIN, "predominant_color_file", service_data)
    await hass.async_block_till_done()

    state = hass.states.get(LIGHT_ENTITY)

    assert state

    # Ensure we turned it on
    assert state.state == STATE_ON

    # And set the brightness
    assert state.attributes[ATTR_BRIGHTNESS] == 255

    assert state.attributes.get(ATTR_RGB_COLOR) != (255, 63, 111)

    # Ensure the RGB values are correct
    # TODO: Get this working again...
    # assert _close_enough(state.attributes[ATTR_RGB_COLOR], (25, 75, 125))
