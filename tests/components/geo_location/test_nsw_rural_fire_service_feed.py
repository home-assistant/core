"""The tests for the geojson platform."""
import datetime
import unittest
from unittest import mock
from unittest.mock import patch, MagicMock

from homeassistant.components import geo_location
from homeassistant.components.geo_location import ATTR_SOURCE
from homeassistant.components.geo_location.nsw_rural_fire_service_feed import \
    ATTR_EXTERNAL_ID, SCAN_INTERVAL, ATTR_CATEGORY, ATTR_FIRE, ATTR_LOCATION, \
    ATTR_COUNCIL_AREA, ATTR_STATUS, ATTR_TYPE, ATTR_SIZE, \
    ATTR_RESPONSIBLE_AGENCY, ATTR_PUBLICATION_DATE
from homeassistant.const import CONF_URL, EVENT_HOMEASSISTANT_START, \
    CONF_RADIUS, ATTR_LATITUDE, ATTR_LONGITUDE, ATTR_FRIENDLY_NAME, \
    ATTR_UNIT_OF_MEASUREMENT, ATTR_ATTRIBUTION
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant, assert_setup_component, \
    fire_time_changed
import homeassistant.util.dt as dt_util

URL = 'http://geo.json.local/geo_json_events.json'
CONFIG = {
    geo_location.DOMAIN: [
        {
            'platform': 'nsw_rural_fire_service_feed',
            CONF_URL: URL,
            CONF_RADIUS: 200
        }
    ]
}


class TestGeoJsonPlatform(unittest.TestCase):
    """Test the geojson platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @staticmethod
    def _generate_mock_feed_entry(external_id, title, distance_to_home,
                                  coordinates, category=None, location=None,
                                  attribution=None, publication_date=None,
                                  council_area=None, status=None,
                                  entry_type=None, fire=True, size=None,
                                  responsible_agency=None):
        """Construct a mock feed entry for testing purposes."""
        feed_entry = MagicMock()
        feed_entry.external_id = external_id
        feed_entry.title = title
        feed_entry.distance_to_home = distance_to_home
        feed_entry.coordinates = coordinates
        feed_entry.category = category
        feed_entry.location = location
        feed_entry.attribution = attribution
        feed_entry.publication_date = publication_date
        feed_entry.council_area = council_area
        feed_entry.status = status
        feed_entry.type = entry_type
        feed_entry.fire = fire
        feed_entry.size = size
        feed_entry.responsible_agency = responsible_agency
        return feed_entry

    @mock.patch('geojson_client.nsw_rural_fire_service_feed.'
                'NswRuralFireServiceFeed')
    def test_setup(self, mock_feed):
        """Test the general setup of the platform."""
        # Set up some mock feed entries for this test.
        mock_entry_1 = self._generate_mock_feed_entry(
            '1234', 'Title 1', 15.5, (-31.0, 150.0), category='Category 1',
            location='Location 1', attribution='Attribution 1',
            publication_date=datetime.datetime(2018, 9, 22, 8, 0,
                                               tzinfo=datetime.timezone.utc),
            council_area='Council Area 1', status='Status 1',
            entry_type='Type 1', size='Size 1', responsible_agency='Agency 1')
        mock_entry_2 = self._generate_mock_feed_entry('2345', 'Title 2', 20.5,
                                                      (-31.1, 150.1),
                                                      fire=False)
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
                self.assertTrue(setup_component(self.hass, geo_location.DOMAIN,
                                                CONFIG))
                # Artificially trigger update.
                self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
                # Collect events.
                self.hass.block_till_done()

                all_states = self.hass.states.all()
                assert len(all_states) == 3

                state = self.hass.states.get("geo_location.title_1")
                self.assertIsNotNone(state)
                assert state.name == "Title 1"
                assert state.attributes == {
                    ATTR_EXTERNAL_ID: "1234", ATTR_LATITUDE: -31.0,
                    ATTR_LONGITUDE: 150.0, ATTR_FRIENDLY_NAME: "Title 1",
                    ATTR_CATEGORY: "Category 1", ATTR_LOCATION: "Location 1",
                    ATTR_ATTRIBUTION: "Attribution 1",
                    ATTR_PUBLICATION_DATE:
                        datetime.datetime(2018, 9, 22, 8, 0,
                                          tzinfo=datetime.timezone.utc),
                    ATTR_FIRE: True,
                    ATTR_COUNCIL_AREA: 'Council Area 1',
                    ATTR_STATUS: 'Status 1', ATTR_TYPE: 'Type 1',
                    ATTR_SIZE: 'Size 1', ATTR_RESPONSIBLE_AGENCY: 'Agency 1',
                    ATTR_UNIT_OF_MEASUREMENT: "km",
                    ATTR_SOURCE: 'nsw_rural_fire_service_feed'}
                self.assertAlmostEqual(float(state.state), 15.5)

                state = self.hass.states.get("geo_location.title_2")
                self.assertIsNotNone(state)
                assert state.name == "Title 2"
                assert state.attributes == {
                    ATTR_EXTERNAL_ID: "2345", ATTR_LATITUDE: -31.1,
                    ATTR_LONGITUDE: 150.1, ATTR_FRIENDLY_NAME: "Title 2",
                    ATTR_FIRE: False,
                    ATTR_UNIT_OF_MEASUREMENT: "km",
                    ATTR_SOURCE: 'nsw_rural_fire_service_feed'}
                self.assertAlmostEqual(float(state.state), 20.5)

                state = self.hass.states.get("geo_location.title_3")
                self.assertIsNotNone(state)
                assert state.name == "Title 3"
                assert state.attributes == {
                    ATTR_EXTERNAL_ID: "3456", ATTR_LATITUDE: -31.2,
                    ATTR_LONGITUDE: 150.2, ATTR_FRIENDLY_NAME: "Title 3",
                    ATTR_FIRE: True,
                    ATTR_UNIT_OF_MEASUREMENT: "km",
                    ATTR_SOURCE: 'nsw_rural_fire_service_feed'}
                self.assertAlmostEqual(float(state.state), 25.5)

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
                                  2 * SCAN_INTERVAL)
                self.hass.block_till_done()

                all_states = self.hass.states.all()
                assert len(all_states) == 0
