"""The test for the geo rss events sensor platform."""
import datetime
import unittest

from tests.common import load_fixture, get_test_home_assistant
import homeassistant.components.sensor.geo_rss_events as geo_rss_events
import pytz

VALID_CONFIG = {
    'platform': 'geo_rss_events',
    geo_rss_events.CONF_URL: 'url'
}


class TestGeoRssServiceUpdater(unittest.TestCase):
    """Test the GeoRss service updater."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_filter_entries(self):
        """Test filtering entries"""
        import feedparser
        updater = self.setup_updater()
        raw_data = load_fixture('geo_rss_events.xml')
        feed_data = feedparser.parse(raw_data)
        filtered_entries = updater.filter_entries(feed_data)
        assert len(filtered_entries) == 3
        assert filtered_entries[0].title == "Title 1"
        assert filtered_entries[0].category == "Category 1"
        assert filtered_entries[0].description == "Description 1"
        assert filtered_entries[0].guid == "GUID 1"
        assert filtered_entries[0].pub_date \
               == datetime.datetime(2017, 7, 30, 9, 0, 0,
                                    tzinfo=pytz.utc).timetuple()

    def setup_updater(self):
        home_latitude = -33.865
        home_longitude = 151.209444
        radius_in_km = 500
        url = ''
        devices = []
        updater = geo_rss_events.GeoRssServiceUpdater(self.hass, None,
                                                         home_latitude,
                                                         home_longitude,
                                                         url, radius_in_km,
                                                         devices)
        return updater
