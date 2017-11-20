"""The tests for the Remote component, adapted from Light Test."""
# pylint: disable=protected-access

import unittest

from homeassistant.setup import setup_component
from homeassistant.const import (
    ATTR_ENTITY_ID, STATE_ON, STATE_OFF, CONF_PLATFORM,
    SERVICE_TURN_ON, SERVICE_TURN_OFF)
import homeassistant.components.remote as remote

from tests.common import mock_service, get_test_home_assistant
TEST_PLATFORM = {remote.DOMAIN: {CONF_PLATFORM: 'test'}}
SERVICE_SEND_COMMAND = 'send_command'


class TestRemote(unittest.TestCase):
    """Test the remote module."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_is_on(self):
        """Test is_on."""
        self.hass.states.set('remote.test', STATE_ON)
        self.assertTrue(remote.is_on(self.hass, 'remote.test'))

        self.hass.states.set('remote.test', STATE_OFF)
        self.assertFalse(remote.is_on(self.hass, 'remote.test'))

        self.hass.states.set(remote.ENTITY_ID_ALL_REMOTES, STATE_ON)
        self.assertTrue(remote.is_on(self.hass))

        self.hass.states.set(remote.ENTITY_ID_ALL_REMOTES, STATE_OFF)
        self.assertFalse(remote.is_on(self.hass))

    def test_turn_on(self):
        """Test turn_on."""
        turn_on_calls = mock_service(
            self.hass, remote.DOMAIN, SERVICE_TURN_ON)

        remote.turn_on(
            self.hass,
            entity_id='entity_id_val')

        self.hass.block_till_done()

        self.assertEqual(1, len(turn_on_calls))
        call = turn_on_calls[-1]

        self.assertEqual(remote.DOMAIN, call.domain)

    def test_turn_off(self):
        """Test turn_off."""
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

    def test_send_command(self):
        """Test send_command."""
        send_command_calls = mock_service(
            self.hass, remote.DOMAIN, SERVICE_SEND_COMMAND)

        remote.send_command(
            self.hass, entity_id='entity_id_val',
            device='test_device', command=['test_command'],
            num_repeats='4', delay_secs='0.6')

        self.hass.block_till_done()

        self.assertEqual(1, len(send_command_calls))
        call = send_command_calls[-1]

        self.assertEqual(remote.DOMAIN, call.domain)
        self.assertEqual(SERVICE_SEND_COMMAND, call.service)
        self.assertEqual('entity_id_val', call.data[ATTR_ENTITY_ID])

    def test_services(self):
        """Test the provided services."""
        self.assertTrue(setup_component(self.hass, remote.DOMAIN,
                                        TEST_PLATFORM))
