"""The tests for the geo rss events platform."""
import unittest
from genericpath import exists

from os import remove
from unittest.mock import MagicMock

from homeassistant.components.feedreader import StoredData
from homeassistant.components.geo_location.geo_rss_events import \
    GeoRssFeedManager, DEFAULT_NAME, DEFAULT_SCAN_INTERVAL, \
    CONF_ATTRIBUTES_NAME, CONF_ATTRIBUTES_SOURCE, CONF_ATTRIBUTES_REGEXP, \
    CONF_CUSTOM_ATTRIBUTE, ATTR_TITLE, CONF_FILTERS_ATTRIBUTE, \
    CONF_FILTERS_REGEXP, ATTR_DISTANCE, CONF_CATEGORIES, \
    CONF_ATTRIBUTES, ATTR_ID, ATTR_GEOMETRY, DEFAULT_ICON, \
    DEFAULT_UNIT_OF_MEASUREMENT, DEFAULT_STATE_ATTRIBUTE, ATTR_CATEGORY
from homeassistant.const import CONF_URL, ATTR_LATITUDE, ATTR_FRIENDLY_NAME
from homeassistant.core import callback
from homeassistant.setup import setup_component
from tests.common import load_fixture, get_test_home_assistant, \
    assert_setup_component
import homeassistant.components.geo_location as geo_rss_events

URL = 'http://geo.rss.local/geo_rss_events.xml'
CONFIG_WITHOUT_URL = {
    geo_rss_events.DOMAIN: [
        {
            'platform': 'geo_rss_events'
        }
    ]
}
CONFIG_WITHOUT_CATEGORIES = {
    geo_rss_events.DOMAIN: [
        {
            'platform': 'geo_rss_events',
            CONF_URL: URL
        }
    ]
}
CONFIG_WITH_CATEGORIES = {
    geo_rss_events.DOMAIN: [
        {
            'platform': 'geo_rss_events',
            CONF_URL: URL,
            CONF_CATEGORIES: ['Category 1', 'Category 2']
        }
    ]
}
CONFIG_WITH_CUSTOM_ATTRIBUTES = {
    geo_rss_events.DOMAIN: [
        {
            'platform': 'geo_rss_events',
            CONF_URL: URL,
            CONF_ATTRIBUTES: [{
                CONF_ATTRIBUTES_NAME: ATTR_LATITUDE,
                CONF_ATTRIBUTES_REGEXP: '.*',
                CONF_ATTRIBUTES_SOURCE: 'ignore'
            }]
        }
    ]
}


class TestGeoRssEventsComponent(unittest.TestCase):
    """Test the Geo RSS Events platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        # Delete any previously stored data
        data_file = self.hass.config.path("{}.pickle".format('geo_rss_events'))
        if exists(data_file):
            remove(data_file)

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_invalid_config(self):
        """Test the general setup of this component."""
        with assert_setup_component(0, 'geo_location'):
            self.assertTrue(setup_component(self.hass, geo_rss_events.DOMAIN,
                                            CONFIG_WITHOUT_URL))

    def test_setup_one_feed(self):
        """Test the general setup of this component."""
        with assert_setup_component(1, 'geo_location'):
            self.assertTrue(setup_component(self.hass, geo_rss_events.DOMAIN,
                                            CONFIG_WITHOUT_CATEGORIES))
        assert self.hass.states.get(
            'group.event_service').attributes[ATTR_FRIENDLY_NAME] == \
            DEFAULT_NAME

    def test_setup_with_categories(self):
        """Test the setup with categories explicitly defined."""
        with assert_setup_component(1, 'geo_location'):
            self.assertTrue(setup_component(self.hass, geo_rss_events.DOMAIN,
                                            CONFIG_WITH_CATEGORIES))
        assert self.hass.states.get(
            'group.event_service').attributes[ATTR_FRIENDLY_NAME] == \
            DEFAULT_NAME

    def test_setup_with_invalid_custom_attribute_name(self):
        """Test the setup with categories explicitly defined."""
        with assert_setup_component(1, 'geo_location'):
            self.assertTrue(setup_component(self.hass, geo_rss_events.DOMAIN,
                                            CONFIG_WITH_CUSTOM_ATTRIBUTES))
        assert self.hass.states.get(
            'group.event_service').attributes[ATTR_FRIENDLY_NAME] == \
            DEFAULT_NAME

    def setup_manager(self, url='url', name=DEFAULT_NAME,
                      scan_interval=DEFAULT_SCAN_INTERVAL, categories=None,
                      attributes_definition=None, filters_definition=None,
                      state_attribute=DEFAULT_STATE_ATTRIBUTE,
                      unit_of_measurement=DEFAULT_UNIT_OF_MEASUREMENT,
                      icon=DEFAULT_ICON):
        """Set up data object for use by sensors."""
        devices = []

        @callback
        def add_devices_callback(event):
            """Add recorded devices."""
            devices.append(event)

        if attributes_definition is None:
            attributes_definition = []
        home_latitude = -33.865
        home_longitude = 151.209444
        data_file = self.hass.config.path("{}.pickle".format(
            geo_rss_events.DOMAIN))
        storage = StoredData(data_file)
        radius_in_km = 500
        manager = GeoRssFeedManager(self.hass, add_devices_callback, storage,
                                    scan_interval, name, home_latitude,
                                    home_longitude, url, radius_in_km,
                                    categories, attributes_definition,
                                    filters_definition, state_attribute,
                                    unit_of_measurement, icon)
        manager._update()
        return manager

    def prepare_test(self, url=None, categories=None,
                     attributes_definition=None, filters_definition=None,
                     state_attribute=DEFAULT_STATE_ATTRIBUTE):
        """Run generic test with a configuration as provided."""
        name = "Name 1"
        if url is None:
            url = load_fixture('geo_rss_events.xml')
        manager = self.setup_manager(
            url, name=name, categories=categories,
            attributes_definition=attributes_definition,
            filters_definition=filters_definition,
            state_attribute=state_attribute)
        assert manager.name == name
        assert manager.feed_entries is not None
        group = manager.group
        assert group is not None
        assert group.name == name
        return manager

    def test_update_device(self):
        """Test updating the devices."""
        manager = self.prepare_test(url="")
        # Initial setup with mock entries
        entry1 = {ATTR_ID: "GUID 1", ATTR_TITLE: "Title 1",
                  ATTR_DISTANCE: 10.0, ATTR_GEOMETRY:
                      MagicMock(type='Point', coordinates=[-32, 151])}
        entry2 = {ATTR_ID: "GUID 10", ATTR_TITLE: "Title 10",
                  ATTR_DISTANCE: 12.0, ATTR_GEOMETRY:
                      MagicMock(type='Point', coordinates=[-33, 152])}
        entry3 = {ATTR_ID: "GUID 2", ATTR_TITLE: "Title 2",
                  ATTR_DISTANCE: 14.0, ATTR_GEOMETRY:
                      MagicMock(type='Point', coordinates=[-34, 153])}
        manager._generate_new_devices([entry1, entry2, entry3])
        manager._group_devices()
        devices = manager._managed_devices
        self.assertEqual(3, len(devices))
        assert devices[0].external_id == "GUID 1"
        self.assertAlmostEqual(devices[0].distance, 10.0, 0)
        assert devices[1].external_id == "GUID 10"
        # Update with data from fixture.
        manager._url = load_fixture('geo_rss_events.xml')
        manager._update()
        devices = manager._managed_devices
        self.assertEqual(6, len(devices))
        assert devices[0].external_id == "GUID 1"
        self.assertAlmostEqual(devices[1].distance, 301.737, 0)

    def test_platform(self):
        """Test general update of devices."""
        devices = self.prepare_test()._managed_devices
        self.assertEqual(6, len(devices))

        assert devices[0].external_id == "GUID 1"
        assert devices[0].name == "Title 1"
        assert devices[0].category == "Category 1"
        assert devices[0].custom_attributes == {}
        self.assertAlmostEqual(devices[0].state, 116.782, 0)
        self.assertAlmostEqual(devices[0].distance, 116.782, 0)
        assert devices[0].latitude == -32.916667
        assert devices[0].longitude == 151.75
        assert devices[0].device_state_attributes == {'latitude': -32.916667,
                                                      'longitude': 151.75,
                                                      'external id': "GUID 1",
                                                      'category': "Category 1"}
        assert devices[0].unit_of_measurement == "km"
        assert devices[0].icon == DEFAULT_ICON

        assert devices[1].external_id == "GUID 2"
        assert devices[1].name == "Title 2"
        assert devices[1].category == "Category 2"
        assert devices[1].custom_attributes == {}
        self.assertAlmostEqual(devices[1].state, 301.737, 0)
        self.assertAlmostEqual(devices[1].distance, 301.737, 0)
        assert devices[1].latitude == -32.256944
        assert devices[1].longitude == 148.601111

        assert devices[2].external_id == "GUID 3"
        assert devices[2].name == "Title 3"
        assert devices[2].category == "Category 3"
        assert devices[2].custom_attributes == {}
        self.assertAlmostEqual(devices[2].state, 203.786, 0)
        self.assertAlmostEqual(devices[2].distance, 203.786, 0)
        self.assertAlmostEqual(devices[2].latitude, -33.289, 0)
        self.assertAlmostEqual(devices[2].longitude, 149.106, 0)

        assert devices[3].external_id == "Title 6"
        assert devices[3].name == "Title 6"
        assert devices[3].category == "Category 6"
        assert devices[3].custom_attributes == {}
        self.assertAlmostEqual(devices[3].state, 48.06, 0)
        self.assertAlmostEqual(devices[3].distance, 48.06, 0)
        assert devices[3].latitude == -33.75801
        assert devices[3].longitude == 150.70544

    def test_filter_by_categories(self):
        """Test filtering the feed entries by category."""
        categories = ['Category 6']
        devices = self.prepare_test(categories=categories)._managed_devices
        self.assertEqual(1, len(devices))
        assert devices[0].external_id == "Title 6"

    def test_find_external_id(self):
        """Test to find an external ID for a GeoRSS entry."""
        entry1 = {ATTR_ID: "GUID 1", ATTR_TITLE: "Title 1"}
        external_id1 = GeoRssFeedManager._external_id(entry1)
        assert external_id1 is not None
        assert external_id1 == "GUID 1"

        entry2 = {ATTR_TITLE: "Title 1"}
        external_id2 = GeoRssFeedManager._external_id(entry2)
        assert external_id2 is not None
        assert external_id2 == "Title 1"

    def test_state_attribute(self):
        """Test custom state attribute 'category'."""
        category = 'Category 6'
        categories = [category]
        state_attribute = ATTR_CATEGORY
        devices = self.prepare_test(
            categories=categories,
            state_attribute=state_attribute)._managed_devices
        self.assertEqual(1, len(devices))
        assert devices[0].state == category

    def test_attributes(self):
        """Test extracting a custom attribute."""
        attributes_definition = [{
            CONF_ATTRIBUTES_NAME: 'title_index',
            CONF_ATTRIBUTES_SOURCE: ATTR_TITLE,
            CONF_ATTRIBUTES_REGEXP:
                '(?P<' + CONF_CUSTOM_ATTRIBUTE + '>\d+)'
        }]
        devices = self.prepare_test(
            attributes_definition=attributes_definition)._managed_devices
        self.assertEqual(6, len(devices))

        # Check entries
        assert devices[0].custom_attributes.get('title_index') == '1'
        assert devices[1].custom_attributes.get('title_index') == '2'
        assert devices[2].custom_attributes.get('title_index') == '3'
        assert devices[3].custom_attributes.get('title_index') == '6'
        assert devices[4].custom_attributes.get('title_index') == ''
        assert devices[5].custom_attributes.get('title_index') == '9'

    def test_state_attribute_from_custom_attributes(self):
        """Test custom state attribute 'title_index'."""
        custom_attribute_name = 'title_index'
        attributes_definition = [{
            CONF_ATTRIBUTES_NAME: custom_attribute_name,
            CONF_ATTRIBUTES_SOURCE: ATTR_TITLE,
            CONF_ATTRIBUTES_REGEXP:
                '(?P<' + CONF_CUSTOM_ATTRIBUTE + '>\d+)'
        }]
        state_attribute = custom_attribute_name
        devices = self.prepare_test(
            attributes_definition=attributes_definition,
            state_attribute=state_attribute)._managed_devices
        self.assertEqual(6, len(devices))
        assert devices[0].state == '1'
        assert devices[1].state == '2'
        assert devices[2].state == '3'
        assert devices[3].state == '6'
        assert devices[4].state == ''
        assert devices[5].state == '9'

    def test_attributes_nonexistent_source(self):
        """Test extracting a custom attribute from a nonexistent source."""
        attributes_definition = [{
            CONF_ATTRIBUTES_NAME: 'title_index',
            CONF_ATTRIBUTES_SOURCE: 'nonexistent',
            CONF_ATTRIBUTES_REGEXP:
                '(?P<' + CONF_CUSTOM_ATTRIBUTE + '>\d+)'
        }]
        devices = self.prepare_test(
            attributes_definition=attributes_definition)._managed_devices
        # Check entries
        self.assertEqual(6, len(devices))
        assert devices[0].custom_attributes.get('title_index') is ''
        assert devices[1].custom_attributes.get('title_index') is ''
        assert devices[2].custom_attributes.get('title_index') is ''
        assert devices[3].custom_attributes.get('title_index') is ''
        assert devices[4].custom_attributes.get('title_index') is ''
        assert devices[5].custom_attributes.get('title_index') is ''

    def test_filter(self):
        """Test a custom filter."""
        filters_definition = [{
            CONF_FILTERS_ATTRIBUTE: ATTR_TITLE,
            CONF_FILTERS_REGEXP:
                'Title [3-9]{1}'
        }]
        devices = self.prepare_test(filters_definition=filters_definition)\
            ._managed_devices
        # Check entries
        self.assertEqual(3, len(devices))
        assert devices[0].name == 'Title 3'
        assert devices[1].name == 'Title 6'
        assert devices[2].name == 'Title 9'

    def test_filter_nonexistent_attribute(self):
        """Test a custom filter on non-existent attribute."""
        filters_definition = [{
            CONF_FILTERS_ATTRIBUTE: 'nonexistent',
            CONF_FILTERS_REGEXP: '.*'
        }]
        devices = self.prepare_test(filters_definition=filters_definition)\
            ._managed_devices
        # Check entries
        self.assertEqual(0, len(devices))
