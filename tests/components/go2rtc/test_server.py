"""Tests for the go2rtc server."""

import asyncio
from collections.abc import Generator
import logging
import subprocess
from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.components.go2rtc.server import Server
from homeassistant.core import HomeAssistant

TEST_BINARY = "/bin/go2rtc"


@pytest.fixture
def server(hass: HomeAssistant) -> Server:
    """Fixture to initialize the Server."""
    return Server(hass, binary=TEST_BINARY)


@pytest.fixture
def mock_tempfile() -> Generator[Mock]:
    """Fixture to mock NamedTemporaryFile."""
    with patch(
        "homeassistant.components.go2rtc.server.NamedTemporaryFile", autospec=True
    ) as mock_tempfile:
        file = mock_tempfile.return_value.__enter__.return_value
        file.name = "test.yaml"
        yield file


@pytest.fixture
def mock_process() -> Generator[MagicMock]:
    """Fixture to mock subprocess.Popen."""
    with patch(
        "homeassistant.components.go2rtc.server.asyncio.create_subprocess_exec"
    ) as mock_popen:
        mock_popen.return_value.terminate = MagicMock()
        mock_popen.return_value.kill = MagicMock()
        mock_popen.return_value.returncode = None
        yield mock_popen


async def test_server_run_success(
    mock_process: MagicMock,
    server: Server,
    caplog: pytest.LogCaptureFixture,
    mock_tempfile: Mock,
) -> None:
    """Test that the server runs successfully."""
    # Simulate process output
    mock_process.return_value.stdout.__aiter__.return_value = iter(
        [
            b"log line 1\n",
            b"log line 2\n",
        ]
    )

    await server.start()

    # Check that Popen was called with the right arguments
    mock_process.assert_called_once_with(
        TEST_BINARY,
        "-c",
        "test.yaml",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Verify that the config file was written
    mock_tempfile.write.assert_called_once_with(b"""
api:
  listen: "127.0.0.1:1984"

rtsp:
  listen: ""

webrtc:
  ice_servers: []
""")

    # Check that server read the log lines
    for entry in ("log line 1", "log line 2"):
        assert (
            "homeassistant.components.go2rtc.server",
            logging.DEBUG,
            entry,
        ) in caplog.record_tuples

    await server.stop()
    mock_process.return_value.terminate.assert_called_once()


@pytest.mark.usefixtures("mock_tempfile")
async def test_server_run_process_timeout(
    mock_process: MagicMock, server: Server
) -> None:
    """Test server run where the process takes too long to terminate."""
    mock_process.return_value.stdout.__aiter__.return_value = iter(
        [
            b"log line 1\n",
        ]
    )

    async def sleep() -> None:
        await asyncio.sleep(1)

    # Simulate timeout
    mock_process.return_value.wait.side_effect = sleep

    with patch("homeassistant.components.go2rtc.server._TERMINATE_TIMEOUT", new=0.1):
        # Start server thread
        await server.start()
        await server.stop()

    # Ensure terminate and kill were called due to timeout
    mock_process.return_value.terminate.assert_called_once()
    mock_process.return_value.kill.assert_called_once()
