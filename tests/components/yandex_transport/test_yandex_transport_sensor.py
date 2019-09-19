"""Tests for the yandex transport platform."""

import json
import pytest

import homeassistant.components.sensor as sensor
import homeassistant.util.dt as dt_util
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
from tests.common import (
    assert_setup_component,
    async_setup_component,
    MockDependency,
    load_fixture,
)

REPLY = json.loads(load_fixture("yandex_transport_reply.json"))


@pytest.fixture
def mock_requester():
    """Create a mock ya_ma module and YandexMapsRequester."""
    with MockDependency("ya_ma") as ya_ma:
        instance = ya_ma.YandexMapsRequester.return_value
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


def true_filter(reply, filter_routes=None):
    """Check transport filtering by routes list."""
    closer_time = None
    if filter_routes is None:
        filter_routes = []
    attrs = {}

    stop_metadata = reply["data"]["properties"]["StopMetaData"]

    stop_name = reply["data"]["properties"]["name"]
    transport_list = stop_metadata["Transport"]
    for transport in transport_list:
        route = transport["name"]
        if filter_routes and route not in filter_routes:
            # skip unnecessary route info
            continue
        if "Events" in transport["BriefSchedule"]:
            for event in transport["BriefSchedule"]["Events"]:
                if "Estimated" in event:
                    posix_time_next = int(event["Estimated"]["value"])
                    if closer_time is None or closer_time > posix_time_next:
                        closer_time = posix_time_next
                    if route not in attrs:
                        attrs[route] = []
                    attrs[route].append(event["Estimated"]["text"])
    attrs["stop_name"] = stop_name
    attrs[ATTR_ATTRIBUTION] = "Data provided by maps.yandex.ru"
    if closer_time is None:
        state = None
    else:
        state = dt_util.utc_from_timestamp(closer_time).isoformat(timespec="seconds")
    return attrs, state


async def assert_setup_sensor(hass, config, count=1):
    """Set up the sensor and assert it's been created."""
    with assert_setup_component(count):
        assert await async_setup_component(hass, sensor.DOMAIN, config)


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
    assert state.state == dt_util.utc_from_timestamp(1568659253).isoformat(
        timespec="seconds"
    )


async def test_filtered_attributes(hass, mock_requester):
    """Return the contents of attributes."""
    await assert_setup_sensor(hass, TEST_CONFIG)
    state = hass.states.get("sensor.test_name")

    true_attrs, true_state = true_filter(REPLY, filter_routes=ROUTES)
    assert state.state == true_state
    state_attrs = {key: state.attributes[key] for key in true_attrs}
    assert state_attrs == true_attrs
