"""The tests for the command line notification platform."""
from __future__ import annotations

import os
import subprocess
import tempfile
from unittest.mock import patch

import pytest

from homeassistant import setup
from homeassistant.components.command_line import DOMAIN
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "notify": {
                        "command": "exit 0",
                        "name": "Test2",
                    }
                }
            ]
        }
    ],
)
async def test_setup_integration_yaml(
    hass: HomeAssistant, load_yaml_integration: None
) -> None:
    """Test sensor setup."""
    assert hass.services.has_service(NOTIFY_DOMAIN, "test2")


async def test_bad_config(hass: HomeAssistant) -> None:
    """Test set up the platform with bad/missing configuration."""
    assert await setup.async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {
            NOTIFY_DOMAIN: [
                {"platform": "command_line"},
            ]
        },
    )
    await hass.async_block_till_done()
    assert not hass.services.has_service(NOTIFY_DOMAIN, "test")


async def test_command_line_output(hass: HomeAssistant) -> None:
    """Test the command line output."""
    with tempfile.TemporaryDirectory() as tempdirname:
        filename = os.path.join(tempdirname, "message.txt")
        message = "one, two, testing, testing"
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "notify": {
                            "command": f"cat > {filename}",
                            "name": "Test3",
                        }
                    }
                ]
            },
        )
        await hass.async_block_till_done()

        assert hass.services.has_service(NOTIFY_DOMAIN, "test3")

        await hass.services.async_call(
            NOTIFY_DOMAIN, "test3", {"message": message}, blocking=True
        )
        with open(filename, encoding="UTF-8") as handle:
            # the echo command adds a line break
            assert message == handle.read()


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "notify": {
                        "command": "exit 1",
                        "name": "Test4",
                    }
                }
            ]
        }
    ],
)
async def test_error_for_none_zero_exit_code(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant, load_yaml_integration: None
) -> None:
    """Test if an error is logged for non zero exit codes."""

    await hass.services.async_call(
        NOTIFY_DOMAIN, "test4", {"message": "error"}, blocking=True
    )
    assert "Command failed" in caplog.text
    assert "return code 1" in caplog.text


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "notify": {
                        "command": "sleep 10000",
                        "command_timeout": 0.0000001,
                        "name": "Test5",
                    }
                }
            ]
        }
    ],
)
async def test_timeout(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant, load_yaml_integration: None
) -> None:
    """Test blocking is not forever."""
    await hass.services.async_call(
        NOTIFY_DOMAIN, "test5", {"message": "error"}, blocking=True
    )
    assert "Timeout" in caplog.text


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "notify": {
                        "command": "exit 0",
                        "name": "Test6",
                    }
                }
            ]
        }
    ],
)
async def test_subprocess_exceptions(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant, load_yaml_integration: None
) -> None:
    """Test that notify subprocess exceptions are handled correctly."""

    with patch(
        "homeassistant.components.command_line.notify.subprocess.Popen"
    ) as check_output:
        check_output.return_value.__enter__ = check_output
        check_output.return_value.communicate.side_effect = [
            subprocess.TimeoutExpired("cmd", 10),
            None,
            subprocess.SubprocessError(),
        ]

        await hass.services.async_call(
            NOTIFY_DOMAIN, "test6", {"message": "error"}, blocking=True
        )
        assert check_output.call_count == 2
        assert "Timeout for command" in caplog.text

        await hass.services.async_call(
            NOTIFY_DOMAIN, "test6", {"message": "error"}, blocking=True
        )
        assert check_output.call_count == 4
        assert "Error trying to exec command" in caplog.text
