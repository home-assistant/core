"""The tests for the Shell command component."""
from __future__ import annotations

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from homeassistant.components import shell_command
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.setup import async_setup_component


def mock_process_creator(error: bool = False):
    """Mock a coroutine that creates a process when yielded."""

    async def communicate() -> tuple[bytes, bytes]:
        """Mock a coroutine that runs a process when yielded.

        Returns a tuple of (stdout, stderr).
        """
        return b"I am stdout", b"I am stderr"

    mock_process = MagicMock()
    mock_process.communicate = communicate
    mock_process.returncode = int(error)
    return mock_process


async def test_executing_service(hass: HomeAssistant) -> None:
    """Test if able to call a configured service."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "called.txt")
        assert await async_setup_component(
            hass,
            shell_command.DOMAIN,
            {shell_command.DOMAIN: {"test_service": f"date > {path}"}},
        )
        await hass.async_block_till_done()

        await hass.services.async_call("shell_command", "test_service", blocking=True)
        await hass.async_block_till_done()
        assert os.path.isfile(path)


async def test_config_not_dict(hass: HomeAssistant) -> None:
    """Test that setup fails if config is not a dict."""
    assert not await async_setup_component(
        hass,
        shell_command.DOMAIN,
        {shell_command.DOMAIN: ["some", "weird", "list"]},
    )


async def test_config_not_valid_service_names(hass: HomeAssistant) -> None:
    """Test that setup fails if config contains invalid service names."""
    assert not await async_setup_component(
        hass,
        shell_command.DOMAIN,
        {shell_command.DOMAIN: {"this is invalid because space": "touch bla.txt"}},
    )


@patch("homeassistant.components.shell_command.asyncio.create_subprocess_shell")
async def test_template_render_no_template(mock_call, hass: HomeAssistant) -> None:
    """Ensure shell_commands without templates get rendered properly."""
    mock_call.return_value = mock_process_creator(error=False)

    assert await async_setup_component(
        hass,
        shell_command.DOMAIN,
        {shell_command.DOMAIN: {"test_service": "ls /bin"}},
    )
    await hass.async_block_till_done()

    await hass.services.async_call("shell_command", "test_service", blocking=True)
    await hass.async_block_till_done()
    cmd = mock_call.mock_calls[0][1][0]

    assert mock_call.call_count == 1
    assert cmd == "ls /bin"


@patch("homeassistant.components.shell_command.asyncio.create_subprocess_shell")
async def test_incorrect_template(mock_call, hass: HomeAssistant) -> None:
    """Ensure shell_commands with invalid templates are handled properly."""
    mock_call.return_value = mock_process_creator(error=False)
    assert await async_setup_component(
        hass,
        shell_command.DOMAIN,
        {
            shell_command.DOMAIN: {
                "test_service": ("ls /bin {{ states['invalid/domain'] }}")
            }
        },
    )

    with pytest.raises(TemplateError):
        await hass.services.async_call(
            "shell_command", "test_service", blocking=True, return_response=True
        )

    await hass.async_block_till_done()


@patch("homeassistant.components.shell_command.asyncio.create_subprocess_exec")
async def test_template_render(mock_call, hass: HomeAssistant) -> None:
    """Ensure shell_commands with templates get rendered properly."""
    hass.states.async_set("sensor.test_state", "Works")
    mock_call.return_value = mock_process_creator(error=False)
    assert await async_setup_component(
        hass,
        shell_command.DOMAIN,
        {
            shell_command.DOMAIN: {
                "test_service": ("ls /bin {{ states.sensor.test_state.state }}")
            }
        },
    )

    await hass.services.async_call("shell_command", "test_service", blocking=True)

    await hass.async_block_till_done()
    cmd = mock_call.mock_calls[0][1]

    assert mock_call.call_count == 1
    assert cmd == ("ls", "/bin", "Works")


@patch("homeassistant.components.shell_command.asyncio.create_subprocess_shell")
@patch("homeassistant.components.shell_command._LOGGER.error")
async def test_subprocess_error(mock_error, mock_call, hass: HomeAssistant) -> None:
    """Test subprocess that returns an error."""
    mock_call.return_value = mock_process_creator(error=True)
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "called.txt")
        assert await async_setup_component(
            hass,
            shell_command.DOMAIN,
            {shell_command.DOMAIN: {"test_service": f"touch {path}"}},
        )

        response = await hass.services.async_call(
            "shell_command", "test_service", blocking=True, return_response=True
        )
        await hass.async_block_till_done()
        assert mock_call.call_count == 1
        assert mock_error.call_count == 1
        assert not os.path.isfile(path)
        assert response["returncode"] == 1


@patch("homeassistant.components.shell_command._LOGGER.debug")
async def test_stdout_captured(mock_output, hass: HomeAssistant) -> None:
    """Test subprocess that has stdout."""
    test_phrase = "I have output"
    assert await async_setup_component(
        hass,
        shell_command.DOMAIN,
        {shell_command.DOMAIN: {"test_service": f"echo {test_phrase}"}},
    )

    response = await hass.services.async_call(
        "shell_command", "test_service", blocking=True, return_response=True
    )

    await hass.async_block_till_done()
    assert mock_output.call_count == 1
    assert test_phrase.encode() + b"\n" == mock_output.call_args_list[0][0][-1]
    assert response["stdout"] == test_phrase
    assert response["returncode"] == 0


@patch("homeassistant.components.shell_command._LOGGER.debug")
async def test_non_text_stdout_capture(
    mock_output, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling of non-text output."""
    assert await async_setup_component(
        hass,
        shell_command.DOMAIN,
        {
            shell_command.DOMAIN: {
                "output_image": "curl -o - https://raw.githubusercontent.com/home-assistant/assets/master/misc/loading-screen.gif"
            }
        },
    )

    # No problem without 'return_response'
    response = await hass.services.async_call(
        "shell_command", "output_image", blocking=True
    )

    await hass.async_block_till_done()
    assert not response

    # Non-text output throws with 'return_response'
    with pytest.raises(UnicodeDecodeError):
        response = await hass.services.async_call(
            "shell_command", "output_image", blocking=True, return_response=True
        )

    await hass.async_block_till_done()
    assert not response
    assert "Unable to handle non-utf8 output of command" in caplog.text


@patch("homeassistant.components.shell_command._LOGGER.debug")
async def test_stderr_captured(mock_output, hass: HomeAssistant) -> None:
    """Test subprocess that has stderr."""
    test_phrase = "I have error"
    assert await async_setup_component(
        hass,
        shell_command.DOMAIN,
        {shell_command.DOMAIN: {"test_service": f">&2 echo {test_phrase}"}},
    )

    response = await hass.services.async_call(
        "shell_command", "test_service", blocking=True, return_response=True
    )

    await hass.async_block_till_done()
    assert mock_output.call_count == 1
    assert test_phrase.encode() + b"\n" == mock_output.call_args_list[0][0][-1]
    assert response["stderr"] == test_phrase


async def test_do_not_run_forever(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test subprocesses terminate after the timeout."""

    async def block():
        event = asyncio.Event()
        await event.wait()
        return (None, None)

    mock_process = Mock()
    mock_process.communicate = block
    mock_process.kill = Mock()
    mock_create_subprocess_shell = AsyncMock(return_value=mock_process)

    assert await async_setup_component(
        hass,
        shell_command.DOMAIN,
        {shell_command.DOMAIN: {"test_service": "mock_sleep 10000"}},
    )
    await hass.async_block_till_done()

    with patch.object(shell_command, "COMMAND_TIMEOUT", 0.001), patch(
        "homeassistant.components.shell_command.asyncio.create_subprocess_shell",
        side_effect=mock_create_subprocess_shell,
    ):
        with pytest.raises(asyncio.TimeoutError):
            await hass.services.async_call(
                shell_command.DOMAIN,
                "test_service",
                blocking=True,
                return_response=True,
            )
        await hass.async_block_till_done()

    mock_process.kill.assert_called_once()
    assert "Timed out" in caplog.text
    assert "mock_sleep 10000" in caplog.text
