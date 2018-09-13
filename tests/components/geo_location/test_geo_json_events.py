"""The tests for the geojson platform."""
import unittest
from unittest import mock
from unittest.mock import patch

from homeassistant.components import geo_location
from homeassistant.components.geo_location.geo_json_events import \
    ATTR_EXTERNAL_ID, ATTR_CATEGORY, CONF_CATEGORIES, DEFAULT_SCAN_INTERVAL
from homeassistant.const import CONF_URL, EVENT_HOMEASSISTANT_START, \
    CONF_RADIUS, ATTR_LATITUDE, ATTR_LONGITUDE, ATTR_UNIT_OF_MEASUREMENT, \
    ATTR_FRIENDLY_NAME
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant, assert_setup_component, \
    load_fixture, fire_time_changed
import homeassistant.util.dt as dt_util

URL = 'http://geo.json.local/geo_json_events1.json'
CONFIG = {
    geo_location.DOMAIN: [
        {
            'platform': 'geo_json_events',
            CONF_URL: URL,
            CONF_RADIUS: 200
        }
    ]
}
CONFIG_WITH_CATEGORY = {
    geo_location.DOMAIN: [
        {
            'platform': 'geo_json_events',
            CONF_URL: URL,
            CONF_RADIUS: 200,
            CONF_CATEGORIES: ["Category 1"]
        }
    ]
}


class TestGeoJsonPlatform(unittest.TestCase):
    """Test the geojson platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        # Set custom home coordinates that are close to the test data.
        self.hass.config.latitude = -31.4
        self.hass.config.longitude = 150.1

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch('homeassistant.components.geo_location.geo_json_events.'
                'RestData')
    def test_setup(self, mock_restdata):
        """Test the general setup of the platform."""
        # Load JSON data from file instead of external URL.
        raw_data = load_fixture('geo_json_events1.json')
        mock_restdata.return_value.data = raw_data

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
                assert len(all_states) == 4

                state = self.hass.states.get("geo_location.title_1")
                self.assertIsNotNone(state)
                assert state.name == "Title 1"
                assert state.attributes == {
                    ATTR_EXTERNAL_ID: "guid 1", ATTR_CATEGORY: "Category 1",
                    ATTR_LATITUDE: -31.456, ATTR_LONGITUDE: 150.123,
                    ATTR_FRIENDLY_NAME: "Title 1",
                    ATTR_UNIT_OF_MEASUREMENT: "km"}
                self.assertAlmostEqual(float(state.state), 6.6)

                state = self.hass.states.get("geo_location.title_2")
                self.assertIsNotNone(state)
                assert state.name == "Title 2"
                assert state.attributes == {
                    ATTR_EXTERNAL_ID: "id 2", ATTR_CATEGORY: "Category 2",
                    ATTR_LATITUDE: -30.53925, ATTR_LONGITUDE: 151.2895,
                    ATTR_FRIENDLY_NAME: "Title 2",
                    ATTR_UNIT_OF_MEASUREMENT: "km"}
                self.assertAlmostEqual(float(state.state), 143.2)

                state = self.hass.states.get("geo_location.title_3")
                self.assertIsNotNone(state)
                assert state.name == "Title 3"
                assert state.attributes == {
                    ATTR_EXTERNAL_ID: "Title 3", ATTR_CATEGORY: "Category 3",
                    ATTR_LATITUDE: -31.567, ATTR_LONGITUDE: 150.234,
                    ATTR_FRIENDLY_NAME: "Title 3",
                    ATTR_UNIT_OF_MEASUREMENT: "km"}
                self.assertAlmostEqual(float(state.state), 22.5)

                state = self.hass.states.get("geo_location.unnamed_device")
                self.assertIsNotNone(state)
                assert state.name == "unnamed device"
                assert state.attributes == {
                    ATTR_EXTERNAL_ID: -5033741844074499516,
                    ATTR_LATITUDE: -31.345, ATTR_LONGITUDE: 150.012,
                    ATTR_UNIT_OF_MEASUREMENT: "km"}
                self.assertAlmostEqual(float(state.state), 10.4)

                # Simulate an update
                raw_data = load_fixture('geo_json_events2.json')
                mock_restdata.return_value.data = raw_data
                fire_time_changed(self.hass, utcnow + DEFAULT_SCAN_INTERVAL)
                self.hass.block_till_done()

                all_states = self.hass.states.all()
                assert len(all_states) == 4

                # 1. Entry must be unchanged
                state = self.hass.states.get("geo_location.title_1")
                self.assertIsNotNone(state)
                assert state.name == "Title 1"
                assert state.attributes == {
                    ATTR_EXTERNAL_ID: "guid 1", ATTR_CATEGORY: "Category 1",
                    ATTR_LATITUDE: -31.456, ATTR_LONGITUDE: 150.123,
                    ATTR_FRIENDLY_NAME: "Title 1",
                    ATTR_UNIT_OF_MEASUREMENT: "km"}
                self.assertAlmostEqual(float(state.state), 6.6)

                # 2. Entry with changed properties
                state = self.hass.states.get("geo_location.title_2")
                self.assertIsNotNone(state)
                assert state.name == "Title 2 Changed"
                assert state.attributes == {
                    ATTR_EXTERNAL_ID: "id 2", ATTR_CATEGORY: "Category 2",
                    ATTR_LATITUDE: -31.568, ATTR_LONGITUDE: 150.235,
                    ATTR_FRIENDLY_NAME: "Title 2 Changed",
                    ATTR_UNIT_OF_MEASUREMENT: "km"}
                self.assertAlmostEqual(float(state.state), 22.6)

                # 3. New Entry
                state = self.hass.states.get("geo_location.title_4")
                self.assertIsNotNone(state)
                assert state.name == "Title 4"
                assert state.attributes == {
                    ATTR_EXTERNAL_ID: "guid 4",
                    ATTR_LATITUDE: -31.678, ATTR_LONGITUDE: 150.345,
                    ATTR_FRIENDLY_NAME: "Title 4",
                    ATTR_UNIT_OF_MEASUREMENT: "km"}
                self.assertAlmostEqual(float(state.state), 38.6)

                # Simulate an update - empty data
                mock_restdata.return_value.data = None
                fire_time_changed(self.hass, utcnow +
                                  2 * DEFAULT_SCAN_INTERVAL)
                self.hass.block_till_done()

                all_states = self.hass.states.all()
                assert len(all_states) == 0

    @mock.patch('homeassistant.components.geo_location.geo_json_events.'
                'RestData')
    def test_setup_with_category(self, mock_restdata):
        """Test the general setup of the platform."""
        # Load JSON data from file instead of external URL.
        raw_data = load_fixture('geo_json_events1.json')
        mock_restdata.return_value.data = raw_data

        with assert_setup_component(1, geo_location.DOMAIN):
            self.assertTrue(setup_component(self.hass, geo_location.DOMAIN,
                                            CONFIG_WITH_CATEGORY))
            # Artificially trigger update.
            self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
            # Collect events.
            self.hass.block_till_done()

            all_states = self.hass.states.all()
            assert len(all_states) == 1

            state = self.hass.states.get("geo_location.title_1")
            self.assertIsNotNone(state)
            assert state.name == "Title 1"
            assert state.attributes == {
                ATTR_EXTERNAL_ID: "guid 1", ATTR_CATEGORY: "Category 1",
                ATTR_LATITUDE: -31.456, ATTR_LONGITUDE: 150.123,
                ATTR_FRIENDLY_NAME: "Title 1", ATTR_UNIT_OF_MEASUREMENT: "km"}
            self.assertAlmostEqual(float(state.state), 6.6)
