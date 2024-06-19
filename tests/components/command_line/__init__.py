"""Tests for command_line component."""

import asyncio
from contextlib import contextmanager
from unittest.mock import MagicMock, patch


@contextmanager
def mock_asyncio_subprocess_run(
    response: bytes = b"", returncode: int = 0, exception: Exception | None = None
):
    """Mock create_subprocess_shell."""

    class MockProcess(asyncio.subprocess.Process):
        @property
        def returncode(self):
            return returncode

        async def communicate(self):
            if exception:
                raise exception
            return response, b""

    mock_process = MockProcess(MagicMock(), MagicMock(), MagicMock())

    with patch(
        "homeassistant.components.command_line.utils.asyncio.create_subprocess_shell",
        return_value=mock_process,
    ) as mock:
        yield mock
