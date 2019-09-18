"""Tests for the yandex transport platform."""

import unittest
from unittest.mock import Mock

import homeassistant.util.dt as dt_util
from homeassistant.components.yandex_transport.sensor import (
    DiscoverMoscowYandexTransport,
    setup_platform,
)
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
from homeassistant.setup import setup_component
from tests.common import assert_setup_component, get_test_home_assistant
from tests.components.yandex_transport import mock_import

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
    ["data"]
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


class TestYandexTransportSensor(unittest.TestCase):
    """Test yandex transport sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_platform_valid_config(self):
        """Check a valid configuration and call add_entities with sensor."""
        with assert_setup_component(1, "sensor"):
            assert setup_component(self.hass, "sensor", TEST_CONFIG)
        add_entities = Mock()
        setup_platform(None, TEST_CONFIG["sensor"], add_entities)
        assert add_entities.called
        assert isinstance(
            add_entities.call_args[0][0][0], DiscoverMoscowYandexTransport
        )

    def test_setup_platform_invalid_config(self):
        """Check an invalid configuration."""
        with assert_setup_component(0):
            assert setup_component(
                self.hass,
                "sensor",
                {"sensor": {"platform": "yandex_transport", "stopid": 1234}},
            )

    def test_name(self):
        """Return the name if set in the configuration."""
        sensor = DiscoverMoscowYandexTransport(mock_import.requester, STOP_ID, [], NAME)
        assert sensor.name == TEST_CONFIG["sensor"][CONF_NAME]

    def test_state(self):
        """Return the contents of _state."""
        sensor = DiscoverMoscowYandexTransport(
            mock_import.requester, STOP_ID, ROUTES, NAME
        )
        sensor.update()
        assert sensor.state == dt_util.utc_from_timestamp(1568659253).isoformat(
            timespec="seconds"
        )

    def test_filtered_attributes(self):
        """Return the contents of attributes."""
        sensor = DiscoverMoscowYandexTransport(
            mock_import.requester, STOP_ID, ROUTES, NAME
        )
        sensor.update()
        attrs, state = true_filter(mock_import.REPLY, filter_routes=ROUTES)
        assert sensor.device_state_attributes == attrs
        assert sensor.state == state
