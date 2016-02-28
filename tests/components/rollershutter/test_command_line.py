"""
tests.components.rollershutter.command_line
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests the command_line component
"""

import os
import tempfile
import unittest
from unittest import mock

import homeassistant.core as ha
import homeassistant.components.rollershutter as rollershutter
from homeassistant.components.rollershutter import (
    command_line as cmd_rs)


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

    def test_state_value(self):
        with tempfile.TemporaryDirectory() as tempdirname:
            path = os.path.join(tempdirname, 'rollershutter_status')
            test_rollershutter = {
                'statecmd': 'cat {}'.format(path),
                'upcmd': 'echo 1 > {}'.format(path),
                'downcmd': 'echo 1 > {}'.format(path),
                'stopcmd': 'echo 0 > {}'.format(path),
                'value_template': '{{ value }}'
            }
            self.assertTrue(rollershutter.setup(self.hass, {
                'rollershutter': {
                    'platform': 'command_line',
                    'rollershutters': {
                        'test': test_rollershutter
                    }
                }
            }))

            state = self.hass.states.get('rollershutter.test')
            self.assertEqual('unknown', state.state)

            rollershutter.move_up(self.hass, 'rollershutter.test')
            self.hass.pool.block_till_done()

            state = self.hass.states.get('rollershutter.test')
            self.assertEqual('open', state.state)

            rollershutter.move_down(self.hass, 'rollershutter.test')
            self.hass.pool.block_till_done()

            state = self.hass.states.get('rollershutter.test')
            self.assertEqual('open', state.state)

            rollershutter.stop(self.hass, 'rollershutter.test')
            self.hass.pool.block_till_done()

            state = self.hass.states.get('rollershutter.test')
            self.assertEqual('closed', state.state)
