"""The test for the geo rss events sensor platform."""
import unittest
from unittest import mock
import sys
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components import sensor
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, ATTR_FRIENDLY_NAME, \
    EVENT_HOMEASSISTANT_START, ATTR_ICON
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant, \
    assert_setup_component, fire_time_changed
import homeassistant.components.sensor.geo_rss_events as geo_rss_events
import homeassistant.util.dt as dt_util

URL = 'http://geo.rss.local/geo_rss_events.xml'
VALID_CONFIG_WITH_CATEGORIES = {
    sensor.DOMAIN: [
        {
            'platform': 'geo_rss_events',
            geo_rss_events.CONF_URL: URL,
            geo_rss_events.CONF_CATEGORIES: [
                'Category 1'
            ]
        }
    ]
}
VALID_CONFIG = {
    sensor.DOMAIN: [
        {
            'platform': 'geo_rss_events',
            geo_rss_events.CONF_URL: URL
        }
    ]
}


# Until https://github.com/kurtmckee/feedparser/pull/131 is released.
@pytest.mark.skipif(sys.version_info[:2] >= (3, 7),
                    reason='Package incompatible with Python 3.7')
class TestGeoRssServiceUpdater(unittest.TestCase):
    """Test the GeoRss service updater."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        # self.config = VALID_CONFIG_WITHOUT_CATEGORIES

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @staticmethod
    def _generate_mock_feed_entry(external_id, title, distance_to_home,
                                  coordinates, category):
        """Construct a mock feed entry for testing purposes."""
        feed_entry = MagicMock()
        feed_entry.external_id = external_id
        feed_entry.title = title
        feed_entry.distance_to_home = distance_to_home
        feed_entry.coordinates = coordinates
        feed_entry.category = category
        return feed_entry

    @mock.patch('georss_client.generic_feed.GenericFeed')
    def test_setup(self, mock_feed):
        """Test the general setup of the platform."""
        # Set up some mock feed entries for this test.
        mock_entry_1 = self._generate_mock_feed_entry('1234', 'Title 1', 15.5,
                                                      (-31.0, 150.0),
                                                      'Category 1')
        mock_entry_2 = self._generate_mock_feed_entry('2345', 'Title 2', 20.5,
                                                      (-31.1, 150.1),
                                                      'Category 1')
        mock_feed.return_value.update.return_value = 'OK', [mock_entry_1,
                                                            mock_entry_2]

        utcnow = dt_util.utcnow()
        # Patching 'utcnow' to gain more control over the timed update.
        with patch('homeassistant.util.dt.utcnow', return_value=utcnow):
            with assert_setup_component(1, sensor.DOMAIN):
                self.assertTrue(setup_component(self.hass, sensor.DOMAIN,
                                                VALID_CONFIG))
                # Artificially trigger update.
                self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
                # Collect events.
                self.hass.block_till_done()

                all_states = self.hass.states.all()
                assert len(all_states) == 1

                state = self.hass.states.get("sensor.event_service_any")
                self.assertIsNotNone(state)
                assert state.name == "Event Service Any"
                assert int(state.state) == 2
                assert state.attributes == {
                    ATTR_FRIENDLY_NAME: "Event Service Any",
                    ATTR_UNIT_OF_MEASUREMENT: "Events",
                    ATTR_ICON: "mdi:alert",
                    "Title 1": "16km", "Title 2": "20km"}

                # Simulate an update - empty data, but successful update,
                # so no changes to entities.
                mock_feed.return_value.update.return_value = 'OK_NO_DATA', None
                fire_time_changed(self.hass, utcnow +
                                  geo_rss_events.SCAN_INTERVAL)
                self.hass.block_till_done()

                all_states = self.hass.states.all()
                assert len(all_states) == 1
                state = self.hass.states.get("sensor.event_service_any")
                assert int(state.state) == 2

                # Simulate an update - empty data, removes all entities
                mock_feed.return_value.update.return_value = 'ERROR', None
                fire_time_changed(self.hass, utcnow +
                                  2 * geo_rss_events.SCAN_INTERVAL)
                self.hass.block_till_done()

                all_states = self.hass.states.all()
                assert len(all_states) == 1
                state = self.hass.states.get("sensor.event_service_any")
                assert int(state.state) == 0
                assert state.attributes == {
                    ATTR_FRIENDLY_NAME: "Event Service Any",
                    ATTR_UNIT_OF_MEASUREMENT: "Events",
                    ATTR_ICON: "mdi:alert"}

    @mock.patch('georss_client.generic_feed.GenericFeed')
    def test_setup_with_categories(self, mock_feed):
        """Test the general setup of the platform."""
        # Set up some mock feed entries for this test.
        mock_entry_1 = self._generate_mock_feed_entry('1234', 'Title 1', 15.5,
                                                      (-31.0, 150.0),
                                                      'Category 1')
        mock_entry_2 = self._generate_mock_feed_entry('2345', 'Title 2', 20.5,
                                                      (-31.1, 150.1),
                                                      'Category 1')
        mock_feed.return_value.update.return_value = 'OK', [mock_entry_1,
                                                            mock_entry_2]

        with assert_setup_component(1, sensor.DOMAIN):
            self.assertTrue(setup_component(self.hass, sensor.DOMAIN,
                                            VALID_CONFIG_WITH_CATEGORIES))
            # Artificially trigger update.
            self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
            # Collect events.
            self.hass.block_till_done()

            all_states = self.hass.states.all()
            assert len(all_states) == 1

            state = self.hass.states.get("sensor.event_service_category_1")
            self.assertIsNotNone(state)
            assert state.name == "Event Service Category 1"
            assert int(state.state) == 2
            assert state.attributes == {
                ATTR_FRIENDLY_NAME: "Event Service Category 1",
                ATTR_UNIT_OF_MEASUREMENT: "Events",
                ATTR_ICON: "mdi:alert",
                "Title 1": "16km", "Title 2": "20km"}
