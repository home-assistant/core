"""The testd for Core components."""
# pylint: disable=protected-access,too-many-public-methods
import unittest
from unittest.mock import patch

import homeassistant.core as ha
from homeassistant.const import (
    STATE_ON, STATE_OFF, SERVICE_TURN_ON, SERVICE_TURN_OFF, 
    SERVICE_SET_BRIGHTNESS, SERVICE_TOGGLE)
import homeassistant.components as comps

from tests.common import get_test_home_assistant


class TestComponentsCore(unittest.TestCase):
    """Test homeassistant.components module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.assertTrue(comps.setup(self.hass, {}))

        self.hass.states.set('light.Bowl', STATE_ON)
        self.hass.states.set('light.Ceiling', STATE_OFF)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_is_on(self):
        """Test is_on method."""
        self.assertTrue(comps.is_on(self.hass, 'light.Bowl'))
        self.assertFalse(comps.is_on(self.hass, 'light.Ceiling'))
        self.assertTrue(comps.is_on(self.hass))

    def test_turn_on(self):
        """Test turn_on method."""
        runs = []
        self.hass.services.register(
            'light', SERVICE_TURN_ON, lambda x: runs.append(1))

        comps.turn_on(self.hass, 'light.Ceiling')

        self.hass.pool.block_till_done()

        self.assertEqual(1, len(runs))

    def test_set_brightness(self):
        """Test set_brightness method."""
        runs = []
        self.hass.services.register(
            'light', SERVICE_SET_BRIGHTNESS, lambda x: runs.append(1))

        comps.set_brightness(self.hass, 'light.Bedroom')

        self.hass.pool.block_till_done()

        self.assertEqual(1, len(runs))

    def test_turn_off(self):
        """Test turn_off method."""
        runs = []
        self.hass.services.register(
            'light', SERVICE_TURN_OFF, lambda x: runs.append(1))

        comps.turn_off(self.hass, 'light.Bowl')

        self.hass.pool.block_till_done()

        self.assertEqual(1, len(runs))

    def test_toggle(self):
        """Test toggle method."""
        runs = []
        self.hass.services.register(
            'light', SERVICE_TOGGLE, lambda x: runs.append(1))

        comps.toggle(self.hass, 'light.Bowl')

        self.hass.pool.block_till_done()

        self.assertEqual(1, len(runs))

    @patch('homeassistant.core.ServiceRegistry.call')
    def test_turn_on_to_not_block_for_domains_without_service(self, mock_call):
        """Test if turn_on is blocking domain with no service."""
        self.hass.services.register('light', SERVICE_TURN_ON, lambda x: x)

        # We can't test if our service call results in services being called
        # because by mocking out the call service method, we mock out all
        # So we mimick how the service registry calls services
        service_call = ha.ServiceCall('homeassistant', 'turn_on', {
            'entity_id': ['light.test', 'sensor.bla', 'light.bla']
        })
        self.hass.services._services['homeassistant']['turn_on'](service_call)

        self.assertEqual(2, mock_call.call_count)
        self.assertEqual(
            ('light', 'turn_on', {'entity_id': ['light.bla', 'light.test']},
             True),
            mock_call.call_args_list[0][0])
        self.assertEqual(
            ('sensor', 'turn_on', {'entity_id': ['sensor.bla']}, False),
            mock_call.call_args_list[1][0])
