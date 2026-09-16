"""The tests for the command line notification platform."""

import asyncio
import os
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import setup
from homeassistant.components.command_line import DOMAIN
from homeassistant.components.command_line.notify import CommandLineNotificationService
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


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
        assert message == await hass.async_add_executor_job(Path(filename).read_text)


async def test_command_line_output_single_command(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the command line output."""

    await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            "command_line": [
                {
                    "notify": {
                        "command": "echo",
                        "name": "Test3",
                    }
                }
            ]
        },
    )
    await hass.async_block_till_done()

    assert hass.services.has_service(NOTIFY_DOMAIN, "test3")

    await hass.services.async_call(
        NOTIFY_DOMAIN, "test3", {"message": "test message"}, blocking=True
    )
    assert "Running command: echo" in caplog.text
    assert "Running with message: test message" in caplog.text


async def test_command_template(hass: HomeAssistant) -> None:
    """Test the command line output using template as command."""

    with tempfile.TemporaryDirectory() as tempdirname:
        filename = os.path.join(tempdirname, "message.txt")
        message = "one, two, testing, testing"
        hass.states.async_set("sensor.test_state", filename)
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "notify": {
                            "command": "cat > {{ states.sensor.test_state.state }}",
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
        assert message == await hass.async_add_executor_job(Path(filename).read_text)


async def test_command_incorrect_template(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the command line output using template as command which isn't working."""

    message = "one, two, testing, testing"
    await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            "command_line": [
                {
                    "notify": {
                        "command": "cat > {{ this template doesn't parse ",
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

    assert (
        "Error rendering command template: TemplateSyntaxError: expected token"
        in caplog.text
    )


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
                        "command": "sleep 5",
                        "command_timeout": 0,
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
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            NOTIFY_DOMAIN, "test5", {"message": "error"}, blocking=True
        )
    assert exc_info.value.translation_key == "timeout_error"
    assert exc_info.value.translation_placeholders == {"command": "sleep 5"}
    assert "Timeout" in caplog.text


@pytest.mark.parametrize(
    "message",
    [
        pytest.param("x" * 100000, id="stdin_buffer_below_high_water_mark"),
        pytest.param("x" * 200000, id="stdin_buffer_above_high_water_mark"),
    ],
)
@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "notify": {
                        "command": "sleep 5",
                        "command_timeout": 1,
                        "name": "Test7",
                    }
                }
            ]
        }
    ],
)
@pytest.mark.usefixtures("load_yaml_integration")
async def test_timeout_with_unflushed_stdin(hass: HomeAssistant, message: str) -> None:
    """Test a timeout is raised when the command never drains stdin.

    A message larger than the pipe buffer leaves data queued in the stdin
    transport when the timeout cancels communicate(). The outer timeout keeps a
    regression from hanging the test run instead of failing it.
    """
    with pytest.raises(HomeAssistantError) as exc_info:
        async with asyncio.timeout(3):
            await hass.services.async_call(
                NOTIFY_DOMAIN, "test7", {"message": message}, blocking=True
            )
    assert exc_info.value.translation_key == "timeout_error"
    assert exc_info.value.translation_placeholders == {"command": "sleep 5"}


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
async def test_spawn_error(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant, load_yaml_integration: None
) -> None:
    """Test that a failure to spawn the command is handled correctly."""

    with (
        patch(
            "homeassistant.components.command_line.notify.asyncio.create_subprocess_shell",
            side_effect=OSError("exec failed"),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN, "test6", {"message": "error"}, blocking=True
        )
    assert exc_info.value.translation_key == "command_error"
    assert exc_info.value.translation_placeholders == {
        "command": "exit 0",
        "error": "exec failed",
    }
    assert "Error trying to exec command" in caplog.text


@pytest.mark.parametrize(
    ("is_closing", "write_buffer_size", "expected_abort"),
    [
        pytest.param(True, 0, False, id="stdin_already_closed"),
        pytest.param(True, 4096, True, id="stdin_closing_with_queued_data"),
        pytest.param(False, 0, True, id="stdin_still_connected"),
    ],
)
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
@pytest.mark.usefixtures("load_yaml_integration")
async def test_timeout_cleanup(
    caplog: pytest.LogCaptureFixture,
    hass: HomeAssistant,
    is_closing: bool,
    write_buffer_size: int,
    expected_abort: bool,
) -> None:
    """Test the stdin pipe is only aborted while it can still block wait().

    The command is assumed to have exited between the timeout and the kill, so
    this also covers that kill() raises ProcessLookupError.
    """
    mock_proc = AsyncMock()
    mock_proc.communicate.side_effect = TimeoutError
    mock_proc.kill = MagicMock(side_effect=ProcessLookupError)
    mock_proc.stdin = MagicMock()
    mock_proc.stdin.is_closing.return_value = is_closing
    mock_proc.stdin.transport.get_write_buffer_size.return_value = write_buffer_size

    with (
        patch(
            "homeassistant.components.command_line.notify.asyncio.create_subprocess_shell",
            return_value=mock_proc,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN, "test6", {"message": "error"}, blocking=True
        )
    assert exc_info.value.translation_key == "timeout_error"
    assert exc_info.value.translation_placeholders == {"command": "exit 0"}
    mock_proc.kill.assert_called_once()
    mock_proc.wait.assert_awaited_once()
    assert mock_proc.stdin.transport.abort.called is expected_abort
    assert "Timeout for command" in caplog.text


@pytest.mark.parametrize(
    "kill_side_effect",
    [
        pytest.param(None, id="process_running"),
        # The command may have exited before the kill.
        pytest.param(ProcessLookupError, id="process_already_gone"),
    ],
)
async def test_cancelled_kills_process(
    hass: HomeAssistant, kill_side_effect: type[Exception] | None
) -> None:
    """Test the subprocess is killed and the cancellation is re-raised.

    The event loop reaps the killed child on its own, so the cancellation path
    does not await wait().
    """
    mock_proc = AsyncMock()
    mock_proc.communicate.side_effect = asyncio.CancelledError
    mock_proc.kill = MagicMock(side_effect=kill_side_effect)

    service = CommandLineNotificationService("exit 0", 15)
    service.hass = hass

    with (
        patch(
            "homeassistant.components.command_line.notify.asyncio.create_subprocess_shell",
            return_value=mock_proc,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await service.async_send_message("error")

    mock_proc.kill.assert_called_once()
    mock_proc.wait.assert_not_awaited()
