"""
tests.components.rollershutter.command_rollershutter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests the command_rollershutter component
"""

import unittest
from unittest import mock

import homeassistant.core as ha
from homeassistant.components.rollershutter import (
    command_rollershutter as cmd_rs)


class TestCommandRollerShutter(unittest.TestCase):
    def setup_method(self, method):
        self.hass = ha.HomeAssistant()
        self.hass.config.latitude = 32.87336
        self.hass.config.longitude = 117.22743
        self.rs = cmd_rs.CommandRollershutter(self.hass, 'foo',
                                              'cmd_up', 'cmd_dn',
                                              'cmd_stop', 'cmd_state',
                                              None)  # FIXME

    def teardown_method(self, method):
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_should_poll(self):
        self.assertTrue(self.rs.should_poll)
        self.rs._command_state = None
        self.assertFalse(self.rs.should_poll)

    def test_query_state_value(self):
        with mock.patch('subprocess.check_output') as mock_run:
            mock_run.return_value = b' foo bar '
            result = self.rs._query_state_value('runme')
            self.assertEqual('foo bar', result)
            mock_run.assert_called_once_with('runme', shell=True)



