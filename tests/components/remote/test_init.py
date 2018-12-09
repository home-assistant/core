"""The tests for the Remote component, adapted from Light Test."""
# pylint: disable=protected-access

import unittest

from homeassistant.const import (
    ATTR_ENTITY_ID, STATE_ON, STATE_OFF, CONF_PLATFORM,
    SERVICE_TURN_ON, SERVICE_TURN_OFF)
import homeassistant.components.remote as remote

from tests.common import mock_service, get_test_home_assistant
from tests.components.remote import common

TEST_PLATFORM = {remote.DOMAIN: {CONF_PLATFORM: 'test'}}
SERVICE_SEND_COMMAND = 'send_command'


class TestRemote(unittest.TestCase):
    """Test the remote module."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_is_on(self):
        """Test is_on."""
        self.hass.states.set('remote.test', STATE_ON)
        assert remote.is_on(self.hass, 'remote.test')

        self.hass.states.set('remote.test', STATE_OFF)
        assert not remote.is_on(self.hass, 'remote.test')

        self.hass.states.set(remote.ENTITY_ID_ALL_REMOTES, STATE_ON)
        assert remote.is_on(self.hass)

        self.hass.states.set(remote.ENTITY_ID_ALL_REMOTES, STATE_OFF)
        assert not remote.is_on(self.hass)

    def test_turn_on(self):
        """Test turn_on."""
        turn_on_calls = mock_service(
            self.hass, remote.DOMAIN, SERVICE_TURN_ON)

        common.turn_on(
            self.hass,
            entity_id='entity_id_val')

        self.hass.block_till_done()

        assert 1 == len(turn_on_calls)
        call = turn_on_calls[-1]

        assert remote.DOMAIN == call.domain

    def test_turn_off(self):
        """Test turn_off."""
        turn_off_calls = mock_service(
            self.hass, remote.DOMAIN, SERVICE_TURN_OFF)

        common.turn_off(
            self.hass, entity_id='entity_id_val')

        self.hass.block_till_done()

        assert 1 == len(turn_off_calls)
        call = turn_off_calls[-1]

        assert remote.DOMAIN == call.domain
        assert SERVICE_TURN_OFF == call.service
        assert 'entity_id_val' == call.data[ATTR_ENTITY_ID]

    def test_send_command(self):
        """Test send_command."""
        send_command_calls = mock_service(
            self.hass, remote.DOMAIN, SERVICE_SEND_COMMAND)

        common.send_command(
            self.hass, entity_id='entity_id_val',
            device='test_device', command=['test_command'],
            num_repeats='4', delay_secs='0.6')

        self.hass.block_till_done()

        assert 1 == len(send_command_calls)
        call = send_command_calls[-1]

        assert remote.DOMAIN == call.domain
        assert SERVICE_SEND_COMMAND == call.service
        assert 'entity_id_val' == call.data[ATTR_ENTITY_ID]
