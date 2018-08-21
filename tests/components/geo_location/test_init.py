"""The tests for the geo location component."""
import unittest
from unittest.mock import patch, PropertyMock

from homeassistant.components import geo_location
from homeassistant.components.geo_location import GeoLocationEvent, \
    ATTR_DISTANCE
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.setup import async_setup_component
from tests.common import get_test_home_assistant


async def test_setup_component(hass):
    """Simple test setup of component."""
    result = await async_setup_component(hass, geo_location.DOMAIN)
    assert result


class TestGeoLocationEvent(unittest.TestCase):
    """Test the geo location event class."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_state(self):
        """Test state based on distance."""
        event = GeoLocationEvent()
        self.assertIsNone(event.state)
        with patch("homeassistant.components.geo_location.GeoLocationEvent."
                   "distance", new_callable=PropertyMock) as distance_mock:
            distance_mock.return_value = 5.5
            assert event.state == 5.5

    def test_state_attributes(self):
        """Test state attributes."""
        event = GeoLocationEvent()
        assert event.state_attributes == {}
        with patch("homeassistant.components.geo_location.GeoLocationEvent."
                   "distance", new_callable=PropertyMock) as distance_mock:
            with patch(
                    "homeassistant.components.geo_location.GeoLocationEvent."
                    "latitude", new_callable=PropertyMock) as latitude_mock:
                with patch(
                        "homeassistant.components.geo_location."
                        "GeoLocationEvent.longitude",
                        new_callable=PropertyMock) as longitude_mock:
                    distance_mock.return_value = 5.5
                    latitude_mock.return_value = -33.1
                    longitude_mock.return_value = 151.9
                    assert event.state_attributes == {ATTR_DISTANCE: 5.5,
                                                      ATTR_LATITUDE: -33.1,
                                                      ATTR_LONGITUDE: 151.9}

    def test_device_state_attributes(self):
        """Test device state attributes."""
        event = GeoLocationEvent()
        self.assertIsNone(event.device_state_attributes)
        with patch(
                "homeassistant.components.geo_location.GeoLocationEvent."
                "latitude", new_callable=PropertyMock) as latitude_mock:
            with patch(
                    "homeassistant.components.geo_location."
                    "GeoLocationEvent.longitude",
                    new_callable=PropertyMock) as longitude_mock:
                latitude_mock.return_value = -33.1
                longitude_mock.return_value = 151.9
                assert event.device_state_attributes == {ATTR_LATITUDE: -33.1,
                                                         ATTR_LONGITUDE: 151.9}
