"""The test for the geo rss events sensor platform."""
import unittest
from unittest import mock
import feedparser

from homeassistant.setup import setup_component
from tests.common import load_fixture, get_test_home_assistant
import homeassistant.components.sensor.geo_rss_events as geo_rss_events

URL = 'http://geo.rss.local/geo_rss_events.xml'
VALID_CONFIG_WITH_CATEGORIES = {
    'platform': 'geo_rss_events',
    geo_rss_events.CONF_URL: URL,
    geo_rss_events.CONF_CATEGORIES: [
        'Category 1',
        'Category 2'
    ]
}
VALID_CONFIG_WITHOUT_CATEGORIES = {
    'platform': 'geo_rss_events',
    geo_rss_events.CONF_URL: URL
}


class TestGeoRssServiceUpdater(unittest.TestCase):
    """Test the GeoRss service updater."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG_WITHOUT_CATEGORIES

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch('feedparser.parse', return_value=feedparser.parse(""))
    def test_setup_with_categories(self, mock_parse):
        """Test the general setup of this sensor."""
        self.config = VALID_CONFIG_WITH_CATEGORIES
        self.assertTrue(
            setup_component(self.hass, 'sensor', {'sensor': self.config}))
        self.assertIsNotNone(
            self.hass.states.get('sensor.event_service_category_1'))
        self.assertIsNotNone(
            self.hass.states.get('sensor.event_service_category_2'))

    @mock.patch('feedparser.parse', return_value=feedparser.parse(""))
    def test_setup_without_categories(self, mock_parse):
        """Test the general setup of this sensor."""
        self.assertTrue(
            setup_component(self.hass, 'sensor', {'sensor': self.config}))
        self.assertIsNotNone(self.hass.states.get('sensor.event_service_any'))

    def setup_data(self, url='url'):
        """Set up data object for use by sensors."""
        home_latitude = -33.865
        home_longitude = 151.209444
        radius_in_km = 500
        data = geo_rss_events.GeoRssServiceData(home_latitude,
                                                home_longitude, url,
                                                radius_in_km)
        return data

    def test_update_sensor_with_category(self):
        """Test updating sensor object."""
        raw_data = load_fixture('geo_rss_events.xml')
        # Loading raw data from fixture and plug in to data object as URL
        # works since the third-party feedparser library accepts a URL
        # as well as the actual data.
        data = self.setup_data(raw_data)
        category = "Category 1"
        name = "Name 1"
        unit_of_measurement = "Unit 1"
        sensor = geo_rss_events.GeoRssServiceSensor(category,
                                                    data, name,
                                                    unit_of_measurement)

        sensor.update()
        assert sensor.name == "Name 1 Category 1"
        assert sensor.unit_of_measurement == "Unit 1"
        assert sensor.icon == "mdi:alert"
        assert len(sensor._data.events) == 4
        assert sensor.state == 1
        assert sensor.device_state_attributes == {'Title 1': "117km"}
        # Check entries of first hit
        assert sensor._data.events[0][geo_rss_events.ATTR_TITLE] == "Title 1"
        assert sensor._data.events[0][
                   geo_rss_events.ATTR_CATEGORY] == "Category 1"
        self.assertAlmostEqual(sensor._data.events[0][
                                   geo_rss_events.ATTR_DISTANCE], 116.586, 0)

    def test_update_sensor_without_category(self):
        """Test updating sensor object."""
        raw_data = load_fixture('geo_rss_events.xml')
        data = self.setup_data(raw_data)
        category = None
        name = "Name 2"
        unit_of_measurement = "Unit 2"
        sensor = geo_rss_events.GeoRssServiceSensor(category,
                                                    data, name,
                                                    unit_of_measurement)

        sensor.update()
        assert sensor.name == "Name 2 Any"
        assert sensor.unit_of_measurement == "Unit 2"
        assert sensor.icon == "mdi:alert"
        assert len(sensor._data.events) == 4
        assert sensor.state == 4
        assert sensor.device_state_attributes == {'Title 1': "117km",
                                                  'Title 2': "302km",
                                                  'Title 3': "204km",
                                                  'Title 6': "48km"}

    def test_update_sensor_without_data(self):
        """Test updating sensor object."""
        data = self.setup_data()
        category = None
        name = "Name 3"
        unit_of_measurement = "Unit 3"
        sensor = geo_rss_events.GeoRssServiceSensor(category,
                                                    data, name,
                                                    unit_of_measurement)

        sensor.update()
        assert sensor.name == "Name 3 Any"
        assert sensor.unit_of_measurement == "Unit 3"
        assert sensor.icon == "mdi:alert"
        assert len(sensor._data.events) == 0
        assert sensor.state == 0

    @mock.patch('feedparser.parse', return_value=None)
    def test_update_sensor_with_none_result(self, parse_function):
        """Test updating sensor object."""
        data = self.setup_data("http://invalid.url/")
        category = None
        name = "Name 4"
        unit_of_measurement = "Unit 4"
        sensor = geo_rss_events.GeoRssServiceSensor(category,
                                                    data, name,
                                                    unit_of_measurement)

        sensor.update()
        assert sensor.name == "Name 4 Any"
        assert sensor.unit_of_measurement == "Unit 4"
        assert sensor.state == 0
