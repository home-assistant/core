"""The tests for the System Monitoring component."""
import unittest

from homeassistant.components import system_monitoring
from homeassistant.util.unit_system import METRIC_SYSTEM
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


class TestSystemMonitoring(unittest.TestCase):
    """Test the System Monitoring component."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = METRIC_SYSTEM
        self.assertTrue(setup_component(self.hass, system_monitoring.DOMAIN, {
            'system_monitoring': {
                'platform': 'demo',
            }
        }))

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_value_to_state(self):
        """Test system monitoring resource."""
        state = self.hass.states.get('system_monitoring.cpu_speed')
        assert state is not None

        assert float(state.state) == 1.3

        data = state.attributes
        assert data.get('unit_of_measurement') == 'GHz'

    def test_naming_with_system(self):
        """Test system monitoring resource."""
        state = self.hass.states.get(
            'system_monitoring.server_average_load_15m')
        assert state is not None
