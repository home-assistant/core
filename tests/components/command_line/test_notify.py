"""The tests for the command line notification platform."""
import os
import subprocess
import tempfile
from unittest.mock import patch

from homeassistant import setup
from homeassistant.components.notify import DOMAIN
from homeassistant.helpers.typing import Any, Dict, HomeAssistantType


async def setup_test_service(
    hass: HomeAssistantType, config_dict: Dict[str, Any]
) -> None:
    """Set up a test command line notify service."""
    assert await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {"platform": "command_line", "name": "Test", **config_dict},
            ]
        },
    )
    await hass.async_block_till_done()


async def test_setup(hass: HomeAssistantType) -> None:
    """Test sensor setup."""
    await setup_test_service(hass, {"command": "exit 0"})
    assert hass.services.has_service(DOMAIN, "test")


async def test_bad_config(hass: HomeAssistantType) -> None:
    """Test set up the platform with bad/missing configuration."""
    await setup_test_service(hass, {})
    assert not hass.services.has_service(DOMAIN, "test")


async def test_command_line_output(hass: HomeAssistantType) -> None:
    """Test the command line output."""
    with tempfile.TemporaryDirectory() as tempdirname:
        filename = os.path.join(tempdirname, "message.txt")
        message = "one, two, testing, testing"
        await setup_test_service(
            hass,
            {
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
    caplog: Any, hass: HomeAssistantType
) -> None:
    """Test if an error is logged for non zero exit codes."""
    await setup_test_service(
        hass,
        {
            "command": "exit 1",
        },
    )

    assert await hass.services.async_call(
        DOMAIN, "test", {"message": "error"}, blocking=True
    )
    assert "Command failed" in caplog.text


async def test_timeout(caplog: Any, hass: HomeAssistantType) -> None:
    """Test blocking is not forever."""
    await setup_test_service(
        hass,
        {
            "command": "sleep 10000",
            "command_timeout": 0.0000001,
        },
    )
    assert await hass.services.async_call(
        DOMAIN, "test", {"message": "error"}, blocking=True
    )
    assert "Timeout" in caplog.text


async def test_subprocess_exceptions(caplog: Any, hass: HomeAssistantType) -> None:
    """Test that notify subprocess exceptions are handled correctly."""

    with patch(
        "homeassistant.components.command_line.notify.subprocess.Popen",
        side_effect=[
            subprocess.TimeoutExpired("cmd", 10),
            subprocess.SubprocessError(),
        ],
    ) as check_output:
        await setup_test_service(hass, {"command": "exit 0"})
        assert await hass.services.async_call(
            DOMAIN, "test", {"message": "error"}, blocking=True
        )
        assert check_output.call_count == 1
        assert "Timeout for command" in caplog.text

        assert await hass.services.async_call(
            DOMAIN, "test", {"message": "error"}, blocking=True
        )
        assert check_output.call_count == 2
        assert "Error trying to exec command" in caplog.text
