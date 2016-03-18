"""The tests for the command line notification platform."""
import os
import tempfile
import unittest

from homeassistant import core
import homeassistant.components.notify as notify
from unittest.mock import patch


class TestCommandLine(unittest.TestCase):
    """Test the command line notifications."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = core.HomeAssistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_command_line_output(self):
        """Test the command line output."""
        with tempfile.TemporaryDirectory() as tempdirname:
            filename = os.path.join(tempdirname, 'message.txt')
            message = 'one, two, testing, testing'
            self.assertTrue(notify.setup(self.hass, {
                'notify': {
                    'name': 'test',
                    'platform': 'command_line',
                    'command': 'echo $(cat) > {}'.format(filename)
                }
            }))

            self.hass.services.call('notify', 'test', {'message': message},
                                    blocking=True)

            result = open(filename).read()
            # the echo command adds a line break
            self.assertEqual(result, "{}\n".format(message))

    @patch('homeassistant.components.notify.command_line._LOGGER.error')
    def test_error_for_none_zero_exit_code(self, mock_error):
        """Test if an error if logged for non zero exit codes."""
        self.assertTrue(notify.setup(self.hass, {
            'notify': {
                'name': 'test',
                'platform': 'command_line',
                'command': 'echo $(cat); exit 1'
            }
        }))

        self.hass.services.call('notify', 'test', {'message': 'error'},
                                blocking=True)
        self.assertEqual(1, mock_error.call_count)
