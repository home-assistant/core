"""The tests for the command line notification platform."""
import os
import tempfile
import unittest
from unittest.mock import patch

from homeassistant.bootstrap import setup_component
import homeassistant.components.notify as notify
from tests.common import get_test_home_assistant


class TestCommandLine(unittest.TestCase):
    """Test the command line notifications."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup(self):
        """Test setup."""
        assert setup_component(self.hass, 'notify', {
            'notify': {
                'name': 'test',
                'platform': 'command_line',
                'command': 'echo $(cat); exit 1',
            }})

    def test_bad_config(self):
        """Test set up the platform with bad/missing configuration."""
        self.assertFalse(setup_component(self.hass, notify.DOMAIN, {
            'notify': {
                'name': 'test',
                'platform': 'bad_platform',
            }
        }))

    def test_command_line_output(self):
        """Test the command line output."""
        with tempfile.TemporaryDirectory() as tempdirname:
            filename = os.path.join(tempdirname, 'message.txt')
            message = 'one, two, testing, testing'
            self.assertTrue(setup_component(self.hass, notify.DOMAIN, {
                'notify': {
                    'name': 'test',
                    'platform': 'command_line',
                    'command': 'echo $(cat) > {}'.format(filename)
                }
            }))

            self.assertTrue(
                self.hass.services.call('notify', 'test', {'message': message},
                                        blocking=True)
            )

            result = open(filename).read()
            # the echo command adds a line break
            self.assertEqual(result, "{}\n".format(message))

    @patch('homeassistant.components.notify.command_line._LOGGER.error')
    def test_error_for_none_zero_exit_code(self, mock_error):
        """Test if an error is logged for non zero exit codes."""
        self.assertTrue(setup_component(self.hass, notify.DOMAIN, {
            'notify': {
                'name': 'test',
                'platform': 'command_line',
                'command': 'echo $(cat); exit 1'
            }
        }))

        self.assertTrue(
            self.hass.services.call('notify', 'test', {'message': 'error'},
                                    blocking=True)
        )
        self.assertEqual(1, mock_error.call_count)
