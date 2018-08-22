"""The tests for the demo platform."""
import unittest

from homeassistant.components import geo_location
from homeassistant.components.geo_location.demo import \
    NUMBER_OF_DEMO_DEVICES, DEFAULT_UNIT_OF_MEASUREMENT, \
    DEFAULT_UPDATE_INTERVAL
from homeassistant.const import EVENT_TIME_CHANGED, ATTR_NOW
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant, assert_setup_component
import homeassistant.util.dt as dt_util

CONFIG = {
    geo_location.DOMAIN: [
        {
            'platform': 'demo'
        }
    ]
}


class TestDemoPlatform(unittest.TestCase):
    """Test the demo platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_platform(self):
        """Test setup of demo platform via configuration."""
        with assert_setup_component(1, geo_location.DOMAIN):
            self.assertTrue(setup_component(self.hass, geo_location.DOMAIN,
                                            CONFIG))
        entity_ids = self.hass.states.entity_ids(geo_location.DOMAIN).copy()
        assert len(entity_ids) == NUMBER_OF_DEMO_DEVICES
        state_first_entry = self.hass.states.get(entity_ids[0])
        state_last_entry = self.hass.states.get(entity_ids[-1])
        # Check a single device's attributes.
        self.assertAlmostEqual(state_first_entry.attributes['distance'],
                               float(state_first_entry.state), places=0)
        self.assertAlmostEqual(state_first_entry.attributes['latitude'],
                               self.hass.config.latitude, delta=1.0)
        self.assertAlmostEqual(state_first_entry.attributes['longitude'],
                               self.hass.config.longitude, delta=1.0)
        assert state_first_entry.attributes['unit_of_measurement'] == \
            DEFAULT_UNIT_OF_MEASUREMENT
        # Update (replaces 1 device).
        self.hass.bus.fire(EVENT_TIME_CHANGED,
                           {ATTR_NOW: dt_util.utcnow() +
                            DEFAULT_UPDATE_INTERVAL})
        self.hass.block_till_done()
        entity_ids_updated = self.hass.states.entity_ids(geo_location.DOMAIN)\
            .copy()
        states_last_entry_updated = self.hass.states.get(
            entity_ids_updated[-1])
        # New entry was added to the end of the end of the array.
        assert state_last_entry is not states_last_entry_updated
