"""The tests for the Air Pollutants component."""
import unittest

from homeassistant.components import air_pollutants
from homeassistant.components.air_pollutants import (
    ATTR_AIR_POLLUTANTS_ATTRIBUTION, ATTR_AIR_POLLUTANTS_N2O,
    ATTR_AIR_POLLUTANTS_OZONE, ATTR_AIR_POLLUTANTS_PM_10,
    ATTR_AIR_POLLUTANTS_TEMPERATURE)
from homeassistant.setup import setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM

from tests.common import get_test_home_assistant


class TestAirPollutants(unittest.TestCase):
    """Test the Air Pollutants component."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = METRIC_SYSTEM
        assert setup_component(self.hass, air_pollutants.DOMAIN, {
            'air_pollutants': {
                'platform': 'demo',
            }
        })

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_attributes(self):
        """Test Air Pollutants attributes."""
        state = self.hass.states.get('air_pollutants.demo_air_pollutants_home')
        assert state is not None

        assert state.state == '14'

        data = state.attributes
        assert data.get(ATTR_AIR_POLLUTANTS_PM_10) == 23
        assert data.get(ATTR_AIR_POLLUTANTS_N2O) == 100
        assert data.get(ATTR_AIR_POLLUTANTS_TEMPERATURE) == 12
        assert data.get(ATTR_AIR_POLLUTANTS_OZONE) is None
        assert data.get(ATTR_AIR_POLLUTANTS_ATTRIBUTION) == \
            'Powered by Home Assistant'

    def test_temperature_convert(self):
        """Test temperature conversion."""
        state = self.hass.states.get(
            'air_pollutants.demo_air_pollutants_office')
        assert state is not None

        assert state.state == '4'

        data = state.attributes
        assert data.get(ATTR_AIR_POLLUTANTS_TEMPERATURE) == -15
