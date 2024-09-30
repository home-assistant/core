"""Tests for the go2rtc server."""

import asyncio
from collections.abc import Generator
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.go2rtc.server import Server

TEST_BINARY = "/bin/go2rtc"


@pytest.fixture
def server() -> Server:
    """Fixture to initialize the Server."""
    return Server(binary=TEST_BINARY)


@pytest.fixture
def mock_tempfile() -> Generator[MagicMock]:
    """Fixture to mock NamedTemporaryFile."""
    with patch(
        "homeassistant.components.go2rtc.server.NamedTemporaryFile"
    ) as mock_tempfile:
        mock_tempfile.return_value.__enter__.return_value.name = "test.yaml"
        yield mock_tempfile


@pytest.fixture
def mock_popen() -> Generator[MagicMock]:
    """Fixture to mock subprocess.Popen."""
    with patch("homeassistant.components.go2rtc.server.subprocess.Popen") as mock_popen:
        yield mock_popen


@pytest.mark.usefixtures("mock_tempfile")
async def test_server_run_success(mock_popen: MagicMock, server: Server) -> None:
    """Test that the server runs successfully."""
    mock_process = MagicMock()
    mock_process.poll.return_value = None  # Simulate process running
    # Simulate process output
    mock_process.stdout.readline.side_effect = [
        b"log line 1\n",
        b"log line 2\n",
        b"",
    ]
    mock_popen.return_value.__enter__.return_value = mock_process

    server.start()
    await asyncio.sleep(0)

    # Check that Popen was called with the right arguments
    mock_popen.assert_called_once_with(
        [TEST_BINARY, "-c", "webrtc.ice_servers=[]", "-c", "test.yaml"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Check that server read the log lines
    assert mock_process.stdout.readline.call_count == 3

    server.stop()
    mock_process.terminate.assert_called_once()
    assert not server.is_alive()


@pytest.mark.usefixtures("mock_tempfile")
def test_server_run_process_timeout(mock_popen: MagicMock, server: Server) -> None:
    """Test server run where the process takes too long to terminate."""

    mock_process = MagicMock()
    mock_process.poll.return_value = None  # Simulate process running
    # Simulate process output
    mock_process.stdout.readline.side_effect = [
        b"log line 1\n",
        b"",
    ]
    # Simulate timeout
    mock_process.wait.side_effect = subprocess.TimeoutExpired(cmd="go2rtc", timeout=5)
    mock_popen.return_value.__enter__.return_value = mock_process

    # Start server thread
    server.start()
    server.stop()

    # Ensure terminate and kill were called due to timeout
    mock_process.terminate.assert_called_once()
    mock_process.kill.assert_called_once()
    assert not server.is_alive()
