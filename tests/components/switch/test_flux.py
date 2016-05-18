"""The tests for the Flux switch platform."""
import unittest

from homeassistant.bootstrap import _setup_component
from homeassistant.components.switch import flux
from homeassistant.const import STATE_OFF, STATE_ON
from tests.common import get_test_home_assistant


class TestSwitchFlux(unittest.TestCase):
    """Test the Flux switch platform."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant(0)
        # self.hass.config.components = ['flux', 'sun', 'light']

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_valid_config(self):
        """Test configuration."""
        assert _setup_component(self.hass, 'switch', {
            'switch': {
                'platform': 'flux',
                'name': 'flux',
                'lights': ['light.desk', 'light.lamp']
            }
        })

    def test_invalid_config_no_lights(self):
        """Test configuration."""
        assert not _setup_component(self.hass, 'switch', {
            'switch': {
                'platform': 'flux',
                'name': 'flux'
            }
        })

    def test_one_switch(self):
        """Test with 1 switch."""
        self.hass.config.components = ['flux']
        assert _setup_component(self.hass, 'switch', {
            'switch': {
                'platform': 'flux',
                'name': 'flux',
                'lights': ['light.desk', 'light.lamp']
            }
        })
        state = self.hass.states.get('switch.flux')
        self.assertEqual(STATE_OFF, state.state)
        self.hass.states.set('switch.flux', STATE_ON)
