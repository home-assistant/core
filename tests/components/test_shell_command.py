"""The tests for the Shell command component."""
import os
import tempfile
import unittest
from unittest.mock import patch
from subprocess import SubprocessError

from homeassistant.bootstrap import _setup_component
from homeassistant.components import shell_command

from tests.common import get_test_home_assistant


class TestShellCommand(unittest.TestCase):
    """Test the Shell command component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_executing_service(self):
        """Test if able to call a configured service."""
        with tempfile.TemporaryDirectory() as tempdirname:
            path = os.path.join(tempdirname, 'called.txt')
            assert _setup_component(self.hass, shell_command.DOMAIN, {
                shell_command.DOMAIN: {
                    'test_service': "date > {}".format(path)
                }
            })

            self.hass.services.call('shell_command', 'test_service',
                                    blocking=True)
            self.hass.block_till_done()

            self.assertTrue(os.path.isfile(path))

    def test_config_not_dict(self):
        """Test if config is not a dict."""
        assert not _setup_component(self.hass, shell_command.DOMAIN, {
            shell_command.DOMAIN: ['some', 'weird', 'list']
        })

    def test_config_not_valid_service_names(self):
        """Test if config contains invalid service names."""
        assert not _setup_component(self.hass, shell_command.DOMAIN, {
            shell_command.DOMAIN: {
                'this is invalid because space': 'touch bla.txt'
            }
        })

    def test_template_render_no_template(self):
        """Ensure shell_commands without templates get rendered properly."""
        cmd, shell = shell_command._parse_command(self.hass, 'ls /bin', {})
        self.assertTrue(shell)
        self.assertEqual(cmd, 'ls /bin')

    def test_template_render(self):
        """Ensure shell_commands with templates get rendered properly."""
        self.hass.states.set('sensor.test_state', 'Works')
        cmd, shell = shell_command._parse_command(
            self.hass,
            'ls /bin {{ states.sensor.test_state.state }}', {}
        )
        self.assertFalse(shell, False)
        self.assertEqual(cmd[-1], 'Works')

    def test_invalid_template_fails(self):
        """Test that shell_commands with invalid templates fail."""
        cmd, _shell = shell_command._parse_command(
            self.hass,
            'ls /bin {{ states. .test_state.state }}', {}
        )
        self.assertEqual(cmd, None)

    @patch('homeassistant.components.shell_command.subprocess.call',
           side_effect=SubprocessError)
    @patch('homeassistant.components.shell_command._LOGGER.error')
    def test_subprocess_raising_error(self, mock_call, mock_error):
        """Test subprocess."""
        with tempfile.TemporaryDirectory() as tempdirname:
            path = os.path.join(tempdirname, 'called.txt')
            assert _setup_component(self.hass, shell_command.DOMAIN, {
                shell_command.DOMAIN: {
                    'test_service': "touch {}".format(path)
                }
            })

            self.hass.services.call('shell_command', 'test_service',
                                    blocking=True)

            self.assertFalse(os.path.isfile(path))
            self.assertEqual(1, mock_error.call_count)
