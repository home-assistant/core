"""Tests for the yandex transport platform."""

import json

import pytest

import homeassistant.components.sensor as sensor
from homeassistant.const import CONF_NAME
import homeassistant.util.dt as dt_util

from tests.async_mock import patch
from tests.common import assert_setup_component, async_setup_component, load_fixture

REPLY = json.loads(load_fixture("yandex_transport_reply.json"))


@pytest.fixture
def mock_requester():
    """Create a mock ya_ma module and YandexMapsRequester."""
    with patch("ya_ma.YandexMapsRequester") as requester:
        instance = requester.return_value
        instance.get_stop_info.return_value = REPLY
        yield instance


STOP_ID = 9639579
ROUTES = ["194", "т36", "т47", "м10"]
NAME = "test_name"
TEST_CONFIG = {
    "sensor": {
        "platform": "yandex_transport",
        "stop_id": 9639579,
        "routes": ROUTES,
        "name": NAME,
    }
}

FILTERED_ATTRS = {
    "т36": ["18:25", "18:42", "18:46"],
    "т47": ["18:35", "18:37", "18:40", "18:42"],
    "м10": ["18:20", "18:27", "18:29", "18:41", "18:43"],
    "stop_name": "7-й автобусный парк",
    "attribution": "Data provided by maps.yandex.ru",
}

RESULT_STATE = dt_util.utc_from_timestamp(1583421540).isoformat(timespec="seconds")


async def assert_setup_sensor(hass, config, count=1):
    """Set up the sensor and assert it's been created."""
    with assert_setup_component(count):
        assert await async_setup_component(hass, sensor.DOMAIN, config)
        await hass.async_block_till_done()


async def test_setup_platform_valid_config(hass, mock_requester):
    """Test that sensor is set up properly with valid config."""
    await assert_setup_sensor(hass, TEST_CONFIG)


async def test_setup_platform_invalid_config(hass, mock_requester):
    """Check an invalid configuration."""
    await assert_setup_sensor(
        hass, {"sensor": {"platform": "yandex_transport", "stopid": 1234}}, count=0
    )


async def test_name(hass, mock_requester):
    """Return the name if set in the configuration."""
    await assert_setup_sensor(hass, TEST_CONFIG)
    state = hass.states.get("sensor.test_name")
    assert state.name == TEST_CONFIG["sensor"][CONF_NAME]


async def test_state(hass, mock_requester):
    """Return the contents of _state."""
    await assert_setup_sensor(hass, TEST_CONFIG)
    state = hass.states.get("sensor.test_name")
    assert state.state == RESULT_STATE


async def test_filtered_attributes(hass, mock_requester):
    """Return the contents of attributes."""
    await assert_setup_sensor(hass, TEST_CONFIG)
    state = hass.states.get("sensor.test_name")
    state_attrs = {key: state.attributes[key] for key in FILTERED_ATTRS}
    assert state_attrs == FILTERED_ATTRS
