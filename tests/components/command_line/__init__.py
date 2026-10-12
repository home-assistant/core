"""Tests for command_line component."""

import asyncio
from contextlib import contextmanager
from unittest.mock import MagicMock, patch


def _make_mock_process(
    response: bytes, returncode: int, exception: Exception | None
) -> asyncio.subprocess.Process:
    """Create a mock subprocess with the given response, return code and exception."""

    class MockProcess(asyncio.subprocess.Process):
        @property
        def returncode(self):
            return returncode

        async def communicate(self, input=None):
            if exception:
                raise exception
            return response, b""

    return MockProcess(MagicMock(), MagicMock(), MagicMock())


@contextmanager
def mock_asyncio_subprocess_run(
    response: bytes = b"", returncode: int = 0, exception: Exception | None = None
):
    """Mock create_subprocess_shell and create_subprocess_exec."""
    mock_process = _make_mock_process(response, returncode, exception)

    with (
        patch(
            "homeassistant.components.command_line.utils.asyncio.create_subprocess_shell",
            return_value=mock_process,
        ) as mock_shell,
        patch(
            "homeassistant.components.command_line.utils.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ),
    ):
        yield mock_shell


@contextmanager
def mock_asyncio_subprocess_exec(
    response: bytes = b"", returncode: int = 0, exception: Exception | None = None
):
    """Mock create_subprocess_exec."""
    mock_process = _make_mock_process(response, returncode, exception)

    with patch(
        "homeassistant.components.command_line.utils.asyncio.create_subprocess_exec",
        return_value=mock_process,
    ) as mock:
        yield mock
