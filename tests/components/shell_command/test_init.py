"""The tests for the Shell command component."""
import asyncio
import os
import tempfile
from typing import Tuple
import unittest

from homeassistant.components import shell_command
from homeassistant.setup import setup_component

from tests.async_mock import Mock, patch
from tests.common import get_test_home_assistant


def mock_process_creator(error: bool = False) -> asyncio.coroutine:
    """Mock a coroutine that creates a process when yielded."""

    @asyncio.coroutine
    def communicate() -> Tuple[bytes, bytes]:
        """Mock a coroutine that runs a process when yielded.

        Returns a tuple of (stdout, stderr).
        """
        return b"I am stdout", b"I am stderr"

    mock_process = Mock()
    mock_process.communicate = communicate
    mock_process.returncode = int(error)
    return mock_process


class TestShellCommand(unittest.TestCase):
    """Test the shell_command component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started.

        Also seems to require a child watcher attached to the loop when run
        from pytest.
        """
        self.hass = get_test_home_assistant()
        asyncio.get_child_watcher().attach_loop(self.hass.loop)
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_executing_service(self):
        """Test if able to call a configured service."""
        with tempfile.TemporaryDirectory() as tempdirname:
            path = os.path.join(tempdirname, "called.txt")
            assert setup_component(
                self.hass,
                shell_command.DOMAIN,
                {shell_command.DOMAIN: {"test_service": f"date > {path}"}},
            )

            self.hass.services.call("shell_command", "test_service", blocking=True)
            self.hass.block_till_done()
            assert os.path.isfile(path)

    def test_config_not_dict(self):
        """Test that setup fails if config is not a dict."""
        assert not setup_component(
            self.hass,
            shell_command.DOMAIN,
            {shell_command.DOMAIN: ["some", "weird", "list"]},
        )

    def test_config_not_valid_service_names(self):
        """Test that setup fails if config contains invalid service names."""
        assert not setup_component(
            self.hass,
            shell_command.DOMAIN,
            {shell_command.DOMAIN: {"this is invalid because space": "touch bla.txt"}},
        )

    @patch(
        "homeassistant.components.shell_command.asyncio.subprocess"
        ".create_subprocess_shell"
    )
    def test_template_render_no_template(self, mock_call):
        """Ensure shell_commands without templates get rendered properly."""
        mock_call.return_value = mock_process_creator(error=False)

        assert setup_component(
            self.hass,
            shell_command.DOMAIN,
            {shell_command.DOMAIN: {"test_service": "ls /bin"}},
        )

        self.hass.services.call("shell_command", "test_service", blocking=True)

        self.hass.block_till_done()
        cmd = mock_call.mock_calls[0][1][0]

        assert mock_call.call_count == 1
        assert "ls /bin" == cmd

    @patch(
        "homeassistant.components.shell_command.asyncio.subprocess"
        ".create_subprocess_exec"
    )
    def test_template_render(self, mock_call):
        """Ensure shell_commands with templates get rendered properly."""
        self.hass.states.set("sensor.test_state", "Works")
        mock_call.return_value = mock_process_creator(error=False)
        assert setup_component(
            self.hass,
            shell_command.DOMAIN,
            {
                shell_command.DOMAIN: {
                    "test_service": ("ls /bin {{ states.sensor.test_state.state }}")
                }
            },
        )

        self.hass.services.call("shell_command", "test_service", blocking=True)

        self.hass.block_till_done()
        cmd = mock_call.mock_calls[0][1]

        assert mock_call.call_count == 1
        assert ("ls", "/bin", "Works") == cmd

    @patch(
        "homeassistant.components.shell_command.asyncio.subprocess"
        ".create_subprocess_shell"
    )
    @patch("homeassistant.components.shell_command._LOGGER.error")
    def test_subprocess_error(self, mock_error, mock_call):
        """Test subprocess that returns an error."""
        mock_call.return_value = mock_process_creator(error=True)
        with tempfile.TemporaryDirectory() as tempdirname:
            path = os.path.join(tempdirname, "called.txt")
            assert setup_component(
                self.hass,
                shell_command.DOMAIN,
                {shell_command.DOMAIN: {"test_service": f"touch {path}"}},
            )

            self.hass.services.call("shell_command", "test_service", blocking=True)

            self.hass.block_till_done()
            assert mock_call.call_count == 1
            assert mock_error.call_count == 1
            assert not os.path.isfile(path)

    @patch("homeassistant.components.shell_command._LOGGER.debug")
    def test_stdout_captured(self, mock_output):
        """Test subprocess that has stdout."""
        test_phrase = "I have output"
        assert setup_component(
            self.hass,
            shell_command.DOMAIN,
            {shell_command.DOMAIN: {"test_service": f"echo {test_phrase}"}},
        )

        self.hass.services.call("shell_command", "test_service", blocking=True)

        self.hass.block_till_done()
        assert mock_output.call_count == 1
        assert test_phrase.encode() + b"\n" == mock_output.call_args_list[0][0][-1]

    @patch("homeassistant.components.shell_command._LOGGER.debug")
    def test_stderr_captured(self, mock_output):
        """Test subprocess that has stderr."""
        test_phrase = "I have error"
        assert setup_component(
            self.hass,
            shell_command.DOMAIN,
            {shell_command.DOMAIN: {"test_service": f">&2 echo {test_phrase}"}},
        )

        self.hass.services.call("shell_command", "test_service", blocking=True)

        self.hass.block_till_done()
        assert mock_output.call_count == 1
        assert test_phrase.encode() + b"\n" == mock_output.call_args_list[0][0][-1]
