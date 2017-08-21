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
        """Test filtering entries."""
        import feedparser
        data = self.setup_data()
        raw_data = load_fixture('geo_rss_events.xml')
        feed_data = feedparser.parse(raw_data)
        filtered_entries = data.filter_entries(feed_data)
        # Check the number of entries found
        assert len(filtered_entries) == 4
        # Check entries of first hit
        assert filtered_entries[0].title == "Title 1"
        assert filtered_entries[0].category == "Category 1"
        assert filtered_entries[0].description == "Description 1"
        assert filtered_entries[0].guid == "GUID 1"
        comparison_date0 = datetime.datetime(2017, 7, 30, 9, 0, 0,
                                             tzinfo=pytz.utc).timetuple()
        assert filtered_entries[0].pub_date == comparison_date0
        assert filtered_entries[0].geometry.type == 'Point'
        assert filtered_entries[0].geometry.coordinates == (151.75, -32.916667)
        distance0 = 116.586
        self.assertAlmostEqual(filtered_entries[0].distance, distance0, 0)
        # Check entry with link instead of GUID
        assert filtered_entries[3].guid == "Link 6"
        comparison_date3 = datetime.datetime(2017, 7, 30, 9, 25, 0,
                                             tzinfo=pytz.utc).timetuple()
        assert filtered_entries[3].pub_date == comparison_date3

    def setup_data(self):
        """Set up data object for use by sensors."""
        home_latitude = -33.865
        home_longitude = 151.209444
        radius_in_km = 500
        url = 'url'
        data = geo_rss_events.GeoRssServiceData(self.hass, home_latitude,
                                                home_longitude, url,
                                                radius_in_km)
        return data

    def test_sensors(self):
        """Test sensor object."""
        category1 = "Category 1"
        data1 = self.setup_data()
        name1 = "Name 1"
        unit_of_measurement1 = "Unit 1"
        sensor1 = geo_rss_events.GeoRssServiceSensor(self.hass, category1,
                                                     data1, name1,
                                                     unit_of_measurement1)
        assert sensor1.name == "Category 1"
        assert sensor1.unit_of_measurement == "Unit 1"
        assert sensor1.icon == "mdi:alert"

        data2 = self.setup_data()
        name2 = "Name 2"
        unit_of_measurement2 = "Unit 2"
        sensor2 = geo_rss_events.GeoRssServiceSensor(self.hass, None, data2,
                                                     name2,
                                                     unit_of_measurement2)
        event1 = type('obj', (object,), {'title': 'Title 1', 'distance': 10.0})
        event2 = type('obj', (object,), {'title': 'Title 2', 'distance': 20.0})
        matrix = {'Title 1': "10km", 'Title 2': "20km"}
        sensor2._state = [event1, event2]
        assert sensor2.name == "Any"
        device_state_attributes2 = sensor2.device_state_attributes
        print(device_state_attributes2)
        assert device_state_attributes2["Title 1"] == matrix["Title 1"]
        assert device_state_attributes2["Title 2"] == matrix["Title 2"]
        assert device_state_attributes2 == matrix
