"""The tests the Roller shutter command line platform."""

import os
import tempfile
import unittest
from unittest import mock

from homeassistant.bootstrap import setup_component
import homeassistant.components.rollershutter as rollershutter
from homeassistant.components.rollershutter import (
    command_line as cmd_rs)
from tests.common import get_test_home_assistant


class TestCommandRollerShutter(unittest.TestCase):
    """Test the Roller shutter command line platform."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.latitude = 32.87336
        self.hass.config.longitude = 117.22743
        self.rs = cmd_rs.CommandRollershutter(self.hass, 'foo',
                                              'cmd_up', 'cmd_dn',
                                              'cmd_stop', 'cmd_state',
                                              None)  # FIXME

    def teardown_method(self, method):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_should_poll(self):
        """Test the setting of polling."""
        self.assertTrue(self.rs.should_poll)
        self.rs._command_state = None
        self.assertFalse(self.rs.should_poll)

    def test_query_state_value(self):
        """Test with state value."""
        with mock.patch('subprocess.check_output') as mock_run:
            mock_run.return_value = b' foo bar '
            result = self.rs._query_state_value('runme')
            self.assertEqual('foo bar', result)
            mock_run.assert_called_once_with('runme', shell=True)

    def test_state_value(self):
        """Test with state value."""
        with tempfile.TemporaryDirectory() as tempdirname:
            path = os.path.join(tempdirname, 'rollershutter_status')
            test_rollershutter = {
                'statecmd': 'cat {}'.format(path),
                'upcmd': 'echo 1 > {}'.format(path),
                'downcmd': 'echo 1 > {}'.format(path),
                'stopcmd': 'echo 0 > {}'.format(path),
                'value_template': '{{ value }}'
            }
            self.assertTrue(setup_component(self.hass, rollershutter.DOMAIN, {
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
            self.hass.block_till_done()

            state = self.hass.states.get('rollershutter.test')
            self.assertEqual('open', state.state)

            rollershutter.move_down(self.hass, 'rollershutter.test')
            self.hass.block_till_done()

            state = self.hass.states.get('rollershutter.test')
            self.assertEqual('open', state.state)

            rollershutter.stop(self.hass, 'rollershutter.test')
            self.hass.block_till_done()

            state = self.hass.states.get('rollershutter.test')
            self.assertEqual('closed', state.state)
