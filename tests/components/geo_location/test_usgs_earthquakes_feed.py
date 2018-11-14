"""The tests for the USGS Earthquake Hazards Program Feed platform."""
import datetime
import unittest
from unittest import mock
from unittest.mock import patch, MagicMock

from homeassistant.components import geo_location
from homeassistant.components.geo_location import ATTR_SOURCE
from homeassistant.components.geo_location\
    .usgs_earthquakes_feed import \
    ATTR_ALERT, ATTR_EXTERNAL_ID, SCAN_INTERVAL, ATTR_PLACE, \
    ATTR_MAGNITUDE, ATTR_STATUS, ATTR_TYPE, \
    ATTR_TIME, ATTR_UPDATED, CONF_FEED_TYPE
from homeassistant.const import EVENT_HOMEASSISTANT_START, \
    CONF_RADIUS, ATTR_LATITUDE, ATTR_LONGITUDE, ATTR_FRIENDLY_NAME, \
    ATTR_UNIT_OF_MEASUREMENT, ATTR_ATTRIBUTION, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant, assert_setup_component, \
    fire_time_changed
import homeassistant.util.dt as dt_util

CONFIG = {
    geo_location.DOMAIN: [
        {
            'platform': 'usgs_earthquakes_feed',
            CONF_FEED_TYPE: 'past_hour_m25_earthquakes',
            CONF_RADIUS: 200
        }
    ]
}

CONFIG_WITH_CUSTOM_LOCATION = {
    geo_location.DOMAIN: [
        {
            'platform': 'usgs_earthquakes_feed',
            CONF_FEED_TYPE: 'past_hour_m25_earthquakes',
            CONF_RADIUS: 200,
            CONF_LATITUDE: 15.1,
            CONF_LONGITUDE: 25.2
        }
    ]
}


class TestUsgsEarthquakesFeedPlatform(unittest.TestCase):
    """Test the USGS Earthquake Hazards Program Feed platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @staticmethod
    def _generate_mock_feed_entry(external_id, title, distance_to_home,
                                  coordinates, place=None,
                                  attribution=None, time=None, updated=None,
                                  magnitude=None, status=None,
                                  entry_type=None, alert=None):
        """Construct a mock feed entry for testing purposes."""
        feed_entry = MagicMock()
        feed_entry.external_id = external_id
        feed_entry.title = title
        feed_entry.distance_to_home = distance_to_home
        feed_entry.coordinates = coordinates
        feed_entry.place = place
        feed_entry.attribution = attribution
        feed_entry.time = time
        feed_entry.updated = updated
        feed_entry.magnitude = magnitude
        feed_entry.status = status
        feed_entry.type = entry_type
        feed_entry.alert = alert
        return feed_entry

    @mock.patch('geojson_client.usgs_earthquake_hazards_program_feed.'
                'UsgsEarthquakeHazardsProgramFeed')
    def test_setup(self, mock_feed):
        """Test the general setup of the platform."""
        # Set up some mock feed entries for this test.
        mock_entry_1 = self._generate_mock_feed_entry(
            '1234', 'Title 1', 15.5, (-31.0, 150.0),
            place='Location 1', attribution='Attribution 1',
            time=datetime.datetime(2018, 9, 22, 8, 0,
                                   tzinfo=datetime.timezone.utc),
            updated=datetime.datetime(2018, 9, 22, 9, 0,
                                      tzinfo=datetime.timezone.utc),
            magnitude=5.7, status='Status 1', entry_type='Type 1',
            alert='Alert 1')
        mock_entry_2 = self._generate_mock_feed_entry('2345', 'Title 2', 20.5,
                                                      (-31.1, 150.1))
        mock_entry_3 = self._generate_mock_feed_entry('3456', 'Title 3', 25.5,
                                                      (-31.2, 150.2))
        mock_entry_4 = self._generate_mock_feed_entry('4567', 'Title 4', 12.5,
                                                      (-31.3, 150.3))
        mock_feed.return_value.update.return_value = 'OK', [mock_entry_1,
                                                            mock_entry_2,
                                                            mock_entry_3]

        utcnow = dt_util.utcnow()
        # Patching 'utcnow' to gain more control over the timed update.
        with patch('homeassistant.util.dt.utcnow', return_value=utcnow):
            with assert_setup_component(1, geo_location.DOMAIN):
                assert setup_component(self.hass, geo_location.DOMAIN, CONFIG)
                # Artificially trigger update.
                self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
                # Collect events.
                self.hass.block_till_done()

                all_states = self.hass.states.all()
                assert len(all_states) == 3

                state = self.hass.states.get("geo_location.title_1")
                assert state is not None
                assert state.name == "Title 1"
                assert state.attributes == {
                    ATTR_EXTERNAL_ID: "1234", ATTR_LATITUDE: -31.0,
                    ATTR_LONGITUDE: 150.0, ATTR_FRIENDLY_NAME: "Title 1",
                    ATTR_PLACE: "Location 1",
                    ATTR_ATTRIBUTION: "Attribution 1",
                    ATTR_TIME:
                        datetime.datetime(2018, 9, 22, 8, 0,
                                          tzinfo=datetime.timezone.utc),
                    ATTR_UPDATED:
                        datetime.datetime(2018, 9, 22, 9, 0,
                                          tzinfo=datetime.timezone.utc),
                    ATTR_STATUS: 'Status 1', ATTR_TYPE: 'Type 1',
                    ATTR_ALERT: 'Alert 1', ATTR_MAGNITUDE: 5.7,
                    ATTR_UNIT_OF_MEASUREMENT: "km",
                    ATTR_SOURCE: 'usgs_earthquakes_feed'}
                assert round(abs(float(state.state)-15.5), 7) == 0

                state = self.hass.states.get("geo_location.title_2")
                assert state is not None
                assert state.name == "Title 2"
                assert state.attributes == {
                    ATTR_EXTERNAL_ID: "2345", ATTR_LATITUDE: -31.1,
                    ATTR_LONGITUDE: 150.1, ATTR_FRIENDLY_NAME: "Title 2",
                    ATTR_UNIT_OF_MEASUREMENT: "km",
                    ATTR_SOURCE: 'usgs_earthquakes_feed'}
                assert round(abs(float(state.state)-20.5), 7) == 0

                state = self.hass.states.get("geo_location.title_3")
                assert state is not None
                assert state.name == "Title 3"
                assert state.attributes == {
                    ATTR_EXTERNAL_ID: "3456", ATTR_LATITUDE: -31.2,
                    ATTR_LONGITUDE: 150.2, ATTR_FRIENDLY_NAME: "Title 3",
                    ATTR_UNIT_OF_MEASUREMENT: "km",
                    ATTR_SOURCE: 'usgs_earthquakes_feed'}
                assert round(abs(float(state.state)-25.5), 7) == 0

                # Simulate an update - one existing, one new entry,
                # one outdated entry
                mock_feed.return_value.update.return_value = 'OK', [
                    mock_entry_1, mock_entry_4, mock_entry_3]
                fire_time_changed(self.hass, utcnow + SCAN_INTERVAL)
                self.hass.block_till_done()

                all_states = self.hass.states.all()
                assert len(all_states) == 3

                # Simulate an update - empty data, but successful update,
                # so no changes to entities.
                mock_feed.return_value.update.return_value = 'OK_NO_DATA', None
                # mock_restdata.return_value.data = None
                fire_time_changed(self.hass, utcnow +
                                  2 * SCAN_INTERVAL)
                self.hass.block_till_done()

                all_states = self.hass.states.all()
                assert len(all_states) == 3

                # Simulate an update - empty data, removes all entities
                mock_feed.return_value.update.return_value = 'ERROR', None
                fire_time_changed(self.hass, utcnow +
                                  3 * SCAN_INTERVAL)
                self.hass.block_till_done()

                all_states = self.hass.states.all()
                assert len(all_states) == 0

    @mock.patch('geojson_client.usgs_earthquake_hazards_program_feed.'
                'UsgsEarthquakeHazardsProgramFeed')
    def test_setup_with_custom_location(self, mock_feed):
        """Test the setup with a custom location."""
        # Set up some mock feed entries for this test.
        mock_entry_1 = self._generate_mock_feed_entry('1234', 'Title 1', 20.5,
                                                      (-31.1, 150.1))
        mock_feed.return_value.update.return_value = 'OK', [mock_entry_1]

        with assert_setup_component(1, geo_location.DOMAIN):
            assert setup_component(self.hass, geo_location.DOMAIN,
                                   CONFIG_WITH_CUSTOM_LOCATION)
            # Artificially trigger update.
            self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
            # Collect events.
            self.hass.block_till_done()

            all_states = self.hass.states.all()
            assert len(all_states) == 1

            mock_feed.assert_called_with((15.1, 25.2),
                                         'past_hour_m25_earthquakes',
                                         filter_minimum_magnitude=0.0,
                                         filter_radius=200.0)
