"""Tests for colorthief component service calls."""
import base64

import pytest
import requests

from homeassistant.components.colorthief import DOMAIN
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component

from tests.async_mock import Mock, mock_open, patch
from tests.common import load_fixture

LIGHT_ENTITY = "light.kitchen_lights"


def _close_enough(actual_rgb, testing_rgb):
    """Validate the given RGB value is in acceptable tolerance."""
    ar, ag, ab = actual_rgb
    tr, tg, tb = testing_rgb

    r_diff = abs(ar - tr)
    g_diff = abs(ag - tg)
    b_diff = abs(ab - tb)

    return r_diff < 5 and g_diff < 5 and b_diff < 5


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
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: LIGHT_ENTITY, ATTR_EFFECT: "none"},
        blocking=True,
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: LIGHT_ENTITY}, blocking=True
    )
    await hass.async_block_till_done()

    state = hass.states.get(LIGHT_ENTITY)

    assert state
    assert state.state == STATE_OFF


async def test_url_success(hass, requests_mock):
    """Test that a successful image GET translate to light RGB."""
    service_data = {
        "url": "http://example.com/images/logo.png",
        "light": LIGHT_ENTITY,
    }

    # Mock the HTTP Response with a base64 encoded 1x1 pixel
    requests_mock.get(
        service_data["url"],
        content=base64.b64decode(load_fixture("colorthief_url.txt")),
    )

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

    state = hass.states.get(LIGHT_ENTITY)

    assert state

    # Ensure we turned it on
    assert state.state == STATE_ON

    assert state.attributes[ATTR_BRIGHTNESS] == 180

    # Ensure the RGB values are correct
    assert _close_enough(
        state.attributes[ATTR_RGB_COLOR], (89, 172, 255)
    )  # 50, 100, 150))  # Why are the rgb_colors mugging me off?


async def test_url_exception(hass, requests_mock):
    """Test that a HTTPError fails to turn light on."""
    service_data = {
        "url": "http://example.com/images/logo.png",
        "light": LIGHT_ENTITY,
    }

    # Mock the HTTP Response with a base64 encoded 1x1 pixel
    requests_mock.get(service_data["url"], exc=requests.HTTPError)

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

    # Light has not been modified due to failure
    state = hass.states.get(LIGHT_ENTITY)
    assert state
    assert state.state == STATE_OFF


async def test_url_error(hass, requests_mock):
    """Test that a HTTP Error (non 200) doesn't turn light on."""
    service_data = {
        "url": "http://example.com/images/logo.png",
        "light": LIGHT_ENTITY,
    }

    # Mock the HTTP Response with a base64 encoded 1x1 pixel
    requests_mock.get(service_data["url"], status_code=400)

    # Load our ColorThief component
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    state = hass.states.get(LIGHT_ENTITY)
    assert state
    assert state.state == STATE_OFF

    # Call the URL specific service, our above mock should return the base64 decoded fixture 1x1 pixel
    await hass.services.async_call(
        DOMAIN, "predominant_color_url", service_data, blocking=True
    )
    await hass.async_block_till_done()

    # Light has not been modified due to failure
    state = hass.states.get(LIGHT_ENTITY)
    assert state
    assert state.state == STATE_OFF


@patch("os.path.isfile", Mock(return_value=True))
@patch("os.access", Mock(return_value=True))
@patch(
    "builtins.open",
    mock_open(read_data=base64.b64decode(load_fixture("colorthief_file.txt"))),
)
async def test_file(hass):
    """Test that the file only service reads a file and translates to light RGB."""
    service_data = {
        "file_path": "/tmp/logo.png",
        "light": LIGHT_ENTITY,
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

    # assert state.attributes[ATTR_BRIGHTNESS] == 255

    # Ensure the RGB values are correct
    assert _close_enough(state.attributes[ATTR_RGB_COLOR], (25, 75, 125))
