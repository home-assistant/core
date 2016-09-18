"""The tests the cover command line platform."""

import os
import tempfile
import unittest
from unittest import mock

from homeassistant.bootstrap import setup_component
import homeassistant.components.cover as cover
from homeassistant.components.cover import (
    command_line as cmd_rs)

from tests.common import get_test_home_assistant


class TestCommandCover(unittest.TestCase):
    """Test the cover command line platform."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.rs = cmd_rs.CommandCover(self.hass, 'foo',
                                      'command_open', 'command_close',
                                      'command_stop', 'command_state',
                                      None)

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
            path = os.path.join(tempdirname, 'cover_status')
            test_cover = {
                'command_state': 'cat {}'.format(path),
                'command_open': 'echo 1 > {}'.format(path),
                'command_close': 'echo 1 > {}'.format(path),
                'command_stop': 'echo 0 > {}'.format(path),
                'value_template': '{{ value }}'
            }
            self.assertTrue(setup_component(self.hass, cover.DOMAIN, {
                'cover': {
                    'platform': 'command_line',
                    'covers': {
                        'test': test_cover
                    }
                }
            }))

            state = self.hass.states.get('cover.test')
            self.assertEqual('unknown', state.state)

            cover.open_cover(self.hass, 'cover.test')
            self.hass.block_till_done()

            state = self.hass.states.get('cover.test')
            self.assertEqual('open', state.state)

            cover.close_cover(self.hass, 'cover.test')
            self.hass.block_till_done()

            state = self.hass.states.get('cover.test')
            self.assertEqual('open', state.state)

            cover.stop_cover(self.hass, 'cover.test')
            self.hass.block_till_done()

            state = self.hass.states.get('cover.test')
            self.assertEqual('closed', state.state)
