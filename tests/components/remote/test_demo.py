"""The tests for the demo remote component."""
# pylint: disable=protected-access
import unittest

from homeassistant.setup import setup_component
import homeassistant.components.remote as remote
from homeassistant.const import (
    ATTR_ENTITY_ID, STATE_ON, STATE_OFF, CONF_PLATFORM,
    SERVICE_TURN_ON, SERVICE_TURN_OFF)
from tests.common import get_test_home_assistant, mock_service

SERVICE_SEND_COMMAND = 'send_command'


class TestDemoRemote(unittest.TestCase):
    """Test the demo remote."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.assertTrue(setup_component(self.hass, remote.DOMAIN, {'remote': {
            'platform': 'demo',
        }}))

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_methods(self):
        """Test if methods call the services as expected."""
        self.assertTrue(
            setup_component(self.hass, remote.DOMAIN,
                            {remote.DOMAIN: {CONF_PLATFORM: 'demo'}}))

        # Test is_on
        self.hass.states.set('remote.demo', STATE_ON)
        self.assertTrue(remote.is_on(self.hass, 'remote.demo'))

        self.hass.states.set('remote.demo', STATE_OFF)
        self.assertFalse(remote.is_on(self.hass, 'remote.demo'))

        self.hass.states.set(remote.ENTITY_ID_ALL_REMOTES, STATE_ON)
        self.assertTrue(remote.is_on(self.hass))

        self.hass.states.set(remote.ENTITY_ID_ALL_REMOTES, STATE_OFF)
        self.assertFalse(remote.is_on(self.hass))

    def test_services(self):
        """Test the provided services."""
        # Test turn_on
        turn_on_calls = mock_service(
            self.hass, remote.DOMAIN, SERVICE_TURN_ON)

        remote.turn_on(
            self.hass,
            entity_id='entity_id_val')

        self.hass.block_till_done()

        self.assertEqual(1, len(turn_on_calls))
        call = turn_on_calls[-1]

        self.assertEqual(remote.DOMAIN, call.domain)

        # Test turn_off
        turn_off_calls = mock_service(
            self.hass, remote.DOMAIN, SERVICE_TURN_OFF)

        remote.turn_off(
            self.hass, entity_id='entity_id_val')

        self.hass.block_till_done()

        self.assertEqual(1, len(turn_off_calls))
        call = turn_off_calls[-1]

        self.assertEqual(remote.DOMAIN, call.domain)
        self.assertEqual(SERVICE_TURN_OFF, call.service)
        self.assertEqual('entity_id_val', call.data[ATTR_ENTITY_ID])

        # Test send_command
        send_command_calls = mock_service(
            self.hass, remote.DOMAIN, SERVICE_SEND_COMMAND)

        remote.send_command(
            self.hass, entity_id='entity_id_val',
            device='test_device', command=['test_command'],
            num_repeats='2', delay_secs='0.8')

        self.hass.block_till_done()

        self.assertEqual(1, len(send_command_calls))
        call = send_command_calls[-1]

        self.assertEqual(remote.DOMAIN, call.domain)
        self.assertEqual(SERVICE_SEND_COMMAND, call.service)
        self.assertEqual('entity_id_val', call.data[ATTR_ENTITY_ID])
