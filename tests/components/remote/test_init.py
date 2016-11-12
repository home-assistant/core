"""The tests for the Remote component, adapted from Light Test."""
# pylint: disable=protected-access

import unittest

# from homeassistant.bootstrap import setup_component
# import homeassistant.loader as loader
from homeassistant.const import (
    ATTR_ENTITY_ID, STATE_ON, STATE_OFF, CONF_PLATFORM,
    SERVICE_TURN_ON, SERVICE_TURN_OFF)
import homeassistant.components.remote as remote

from tests.common import mock_service, get_test_home_assistant
TEST_PLATFORM = {remote.DOMAIN: {CONF_PLATFORM: 'test'}}
SERVICE_SYNC = 'sync'


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

    def test_methods(self):
        """Test if methods call the services as expected."""
        # Test is_on
        self.hass.states.set('remote.test', STATE_ON)
        self.assertTrue(remote.is_on(self.hass, 'remote.test'))

        self.hass.states.set('remote.test', STATE_OFF)
        self.assertFalse(remote.is_on(self.hass, 'remote.test'))

        self.hass.states.set(remote.ENTITY_ID_ALL_REMOTES, STATE_ON)
        self.assertTrue(remote.is_on(self.hass))

        self.hass.states.set(remote.ENTITY_ID_ALL_REMOTES, STATE_OFF)
        self.assertFalse(remote.is_on(self.hass))

        # Test turn_on
        turn_on_calls = mock_service(
            self.hass, remote.DOMAIN, SERVICE_TURN_ON)

        remote.turn_on(
            self.hass,
            entity_id='entity_id_val')

        self.hass.block_till_done()

        self.assertEqual(1, len(turn_on_calls))
        call = turn_on_calls[-1]

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

    # def test_services(self):
    #          """Test the provided services."""
    #     self.assertTrue(setup_component(self.hass, remote.DOMAIN,
    #                                     TEST_PLATFORM))
    #
    #     dev1, dev2, dev3 = platform.DEVICES
    #
    #     # Test init
    #     self.assertTrue(remote.is_on(self.hass, dev1.entity_id))
    #     self.assertFalse(remote.is_on(self.hass, dev2.entity_id))
    #     self.assertFalse(remote.is_on(self.hass, dev3.entity_id))
    #
    #     # Test basic turn_on, turn_off, toggle services
    #     remote.turn_off(self.hass, entity_id=dev1.entity_id)
    #     remote.turn_on(self.hass, entity_id=dev2.entity_id)
    #
    #     self.hass.block_till_done()
    #
    #     self.assertFalse(remote.is_on(self.hass, dev1.entity_id))
    #     self.assertTrue(remote.is_on(self.hass, dev2.entity_id))
    #
    #     # turn on all remotes
    #     remote.turn_on(self.hass)
    #
    #     self.hass.block_till_done()
    #
    #     self.assertTrue(remote.is_on(self.hass, dev1.entity_id))
    #     self.assertTrue(remote.is_on(self.hass, dev2.entity_id))
    #     self.assertTrue(remote.is_on(self.hass, dev3.entity_id))
    #
    #     # turn off all remotes
    #     remote.turn_off(self.hass)
    #
    #     self.hass.block_till_done()
    #
    #     self.assertFalse(remote.is_on(self.hass, dev1.entity_id))
    #     self.assertFalse(remote.is_on(self.hass, dev2.entity_id))
    #     self.assertFalse(remote.is_on(self.hass, dev3.entity_id))
