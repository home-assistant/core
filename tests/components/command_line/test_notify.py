"""The tests for the command line notification platform."""
import logging
import os
import tempfile
import unittest
from unittest.mock import patch

import homeassistant.components.notify as notify
from homeassistant.setup import async_setup_component, setup_component

from tests.common import assert_setup_component, get_test_home_assistant


class TestCommandLine(unittest.TestCase):
    """Test the command line notifications."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup(self):
        """Test setup."""
        with assert_setup_component(1) as handle_config:
            assert setup_component(
                self.hass,
                "notify",
                {
                    "notify": {
                        "name": "test",
                        "platform": "command_line",
                        "command": "echo $(cat); exit 1",
                    }
                },
            )
        assert handle_config[notify.DOMAIN]

    def test_bad_config(self):
        """Test set up the platform with bad/missing configuration."""
        config = {notify.DOMAIN: {"name": "test", "platform": "command_line"}}
        with assert_setup_component(0) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert not handle_config[notify.DOMAIN]

    def test_command_line_output(self):
        """Test the command line output."""
        with tempfile.TemporaryDirectory() as tempdirname:
            filename = os.path.join(tempdirname, "message.txt")
            message = "one, two, testing, testing"
            with assert_setup_component(1) as handle_config:
                assert setup_component(
                    self.hass,
                    notify.DOMAIN,
                    {
                        "notify": {
                            "name": "test",
                            "platform": "command_line",
                            "command": f"echo $(cat) > {filename}",
                        }
                    },
                )
            assert handle_config[notify.DOMAIN]

            assert self.hass.services.call(
                "notify", "test", {"message": message}, blocking=True
            )

            with open(filename) as fil:
                # the echo command adds a line break
                assert fil.read() == f"{message}\n"

    @patch("homeassistant.components.command_line.notify._LOGGER.error")
    def test_error_for_none_zero_exit_code(self, mock_error):
        """Test if an error is logged for non zero exit codes."""
        with assert_setup_component(1) as handle_config:
            assert setup_component(
                self.hass,
                notify.DOMAIN,
                {
                    "notify": {
                        "name": "test",
                        "platform": "command_line",
                        "command": "echo $(cat); exit 1",
                    }
                },
            )
        assert handle_config[notify.DOMAIN]

        assert self.hass.services.call(
            "notify", "test", {"message": "error"}, blocking=True
        )
        assert mock_error.call_count == 1


async def test_timeout(hass, caplog):
    """Test we do not block forever."""
    assert await async_setup_component(
        hass,
        notify.DOMAIN,
        {
            "notify": {
                "name": "test",
                "platform": "command_line",
                "command": "sleep 10000",
                "command_timeout": 0.0000001,
            }
        },
    )
    await hass.async_block_till_done()
    assert await hass.services.async_call(
        "notify", "test", {"message": "error"}, blocking=True
    )
    await hass.async_block_till_done()
    assert "Timeout" in caplog.text


async def test_debug_logging_error(hass, caplog):
    """Test that debug logging occurs for errors."""
    assert await async_setup_component(
        hass,
        notify.DOMAIN,
        {
            "notify": {
                "name": "test",
                "platform": "command_line",
                "command": "i_dont_exist",
            }
        },
    )
    await hass.async_block_till_done()
    with caplog.at_level(logging.DEBUG):
        assert await hass.services.async_call(
            "notify", "test", {"message": "error"}, blocking=True
        )
        await hass.async_block_till_done()
        assert "Running command" in caplog.text
        assert "Stderr" in caplog.text
        assert "Stdout" not in caplog.text


async def test_debug_logging_success(hass, caplog):
    """Test that debug logging occurs for success."""
    assert await async_setup_component(
        hass,
        notify.DOMAIN,
        {"notify": {"name": "test", "platform": "command_line", "command": "cat"}},
    )
    await hass.async_block_till_done()
    with caplog.at_level(logging.DEBUG):
        assert await hass.services.async_call(
            "notify", "test", {"message": "success"}, blocking=True
        )
        await hass.async_block_till_done()
        assert "Running command" in caplog.text
        assert "Stdout" in caplog.text
        assert "Stderr" not in caplog.text
