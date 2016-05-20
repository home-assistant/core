"""The tests for the Flux switch platform."""
import unittest

from homeassistant.bootstrap import _setup_component
from homeassistant.components import switch, light
from homeassistant.const import CONF_NAME, CONF_PLATFORM, STATE_OFF, STATE_ON
import homeassistant.loader as loader
import homeassistant.util.dt as dt_util
from tests.common import fire_mqtt_message, fire_time_changed, get_test_home_assistant


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

    def test_valid_config_no_name(self):
        """Test configuration."""
        assert _setup_component(self.hass, 'switch', {
            'switch': {
                'platform': 'flux',
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

    def test_flux(self):
        """Test with 1 switch."""
        # Create lights
        platform = loader.get_component('light.test')
        platform.init()
        self.assertTrue(
            light.setup(self.hass, {light.DOMAIN: {CONF_PLATFORM: 'test'}}))
        dev1, dev2, dev3 = platform.DEVICES
        
        # Create flux switch
        self.assertTrue(
            switch.setup(self.hass, {
                switch.DOMAIN: {CONF_PLATFORM: 'flux',
                                CONF_NAME: 'flux',
                                'lights':[dev1.entity_id]}}))

        # Verify Initial States
        self.assertTrue(light.is_on(self.hass, dev1.entity_id))
        self.assertFalse(switch.is_on(self.hass, 'switch.flux'))

        # Turn on the light so Flux will control it
        light.turn_on(self.hass, entity_id=dev1.entity_id,
                      brightness=200, xy_color=(.4, .6))
        self.hass.pool.block_till_done()
        method, data = dev1.last_call('turn_on')
        self.assertEqual(
            {light.ATTR_XY_COLOR: (.4, .6), light.ATTR_BRIGHTNESS: 200},
            data)

        # Turn on the flux switch
        switch.turn_on(self.hass, 'switch.flux')
        self.hass.pool.block_till_done()
        self.assertTrue(switch.is_on(self.hass, 'switch.flux'))

        # Change the time, verify color change.
        state = self.hass.states.get(dev1.entity_id)
        self.assertEqual(state.attributes.get("brightness"), 200)
        fire_time_changed(self.hass, dt_util.utcnow().replace(hour=10,
                                                              minute=0,
                                                              second=0))
        state = self.hass.states.get(dev1.entity_id)
        self.assertEqual(state.attributes.get("brightness"), 180)
