"""The tests for the command line notification platform."""
from __future__ import annotations

import os
import subprocess
import tempfile
from unittest.mock import patch

from pytest import LogCaptureFixture

from homeassistant import setup
from homeassistant.components.command_line.const import CONF_COMMAND_TIMEOUT
from homeassistant.components.notify import DOMAIN
from homeassistant.const import CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant

from . import setup_test_entity


async def test_setup(hass: HomeAssistant) -> None:
    """Test sensor setup."""
    assert await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {"platform": "command_line", "name": "Test", "command": "exit 0"},
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "test")


async def test_bad_config(hass: HomeAssistant) -> None:
    """Test set up the platform with bad/missing configuration."""
    await setup_test_entity(hass, {})
    assert not hass.services.has_service(DOMAIN, "test")


async def test_command_line_output(hass: HomeAssistant) -> None:
    """Test the command line output."""
    with tempfile.TemporaryDirectory() as tempdirname:
        filename = os.path.join(tempdirname, "message.txt")
        message = "one, two, testing, testing"
        await setup_test_entity(
            hass,
            {
                CONF_PLATFORM: "notify",
                CONF_NAME: "Test",
                CONF_COMMAND_TIMEOUT: 15,
                "command": f"cat > {filename}",
            },
        )

        assert hass.services.has_service(DOMAIN, "test")

        assert await hass.services.async_call(
            DOMAIN, "test", {"message": message}, blocking=True
        )
        with open(filename) as handle:
            # the echo command adds a line break
            assert message == handle.read()


async def test_error_for_none_zero_exit_code(
    caplog: LogCaptureFixture, hass: HomeAssistant
) -> None:
    """Test if an error is logged for non zero exit codes."""
    await setup_test_entity(
        hass,
        {
            CONF_PLATFORM: "notify",
            CONF_NAME: "Test",
            CONF_COMMAND_TIMEOUT: 15,
            "command": "exit 1",
        },
    )

    assert await hass.services.async_call(
        DOMAIN, "test", {"message": "error"}, blocking=True
    )
    assert "Command failed" in caplog.text
    assert "return code 1" in caplog.text


async def test_timeout(caplog: LogCaptureFixture, hass: HomeAssistant) -> None:
    """Test blocking is not forever."""
    await setup_test_entity(
        hass,
        {
            CONF_PLATFORM: "notify",
            CONF_NAME: "Test",
            "command": "sleep 10000",
            "command_timeout": 0.0000001,
        },
    )
    assert await hass.services.async_call(
        DOMAIN, "test", {"message": "error"}, blocking=True
    )
    assert "Timeout" in caplog.text


async def test_subprocess_exceptions(
    caplog: LogCaptureFixture, hass: HomeAssistant
) -> None:
    """Test that notify subprocess exceptions are handled correctly."""

    with patch(
        "homeassistant.components.command_line.util.subprocess.Popen"
    ) as check_output:
        check_output.return_value.__enter__ = check_output
        check_output.return_value.communicate.side_effect = [
            subprocess.TimeoutExpired("cmd", 10),
            None,
            subprocess.SubprocessError(),
        ]

        await setup_test_entity(
            hass,
            {
                CONF_PLATFORM: "notify",
                CONF_NAME: "Test",
                CONF_COMMAND_TIMEOUT: 15,
                "command": "exit 0",
            },
        )
        assert await hass.services.async_call(
            DOMAIN, "test", {"message": "error"}, blocking=True
        )
        assert check_output.call_count == 2
        assert "Timeout for command" in caplog.text

        assert await hass.services.async_call(
            DOMAIN, "test", {"message": "error"}, blocking=True
        )
        assert check_output.call_count == 4
        assert "Error trying to exec command" in caplog.text
