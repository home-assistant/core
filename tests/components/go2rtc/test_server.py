"""Tests for the go2rtc server."""

import asyncio
from collections.abc import Generator
import logging
import subprocess
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from homeassistant.components.go2rtc.server import Server
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

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


async def test_server_run_success(
    mock_create_subprocess: AsyncMock,
    server_stdout: list[str],
    server: Server,
    caplog: pytest.LogCaptureFixture,
    mock_tempfile: Mock,
) -> None:
    """Test that the server runs successfully."""
    await server.start()

    # Check that Popen was called with the right arguments
    mock_create_subprocess.assert_called_once_with(
        TEST_BINARY,
        "-c",
        "test.yaml",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        close_fds=False,
    )

    # Verify that the config file was written
    mock_tempfile.write.assert_called_once_with(b"""
api:
  listen: "127.0.0.1:1984"

rtsp:
  # ffmpeg needs rtsp for opus audio transcoding
  listen: "127.0.0.1:8554"

webrtc:
  ice_servers: []
""")

    # Check that server read the log lines
    for entry in server_stdout:
        assert (
            "homeassistant.components.go2rtc.server",
            logging.DEBUG,
            entry,
        ) in caplog.record_tuples

    await server.stop()
    mock_create_subprocess.return_value.terminate.assert_called_once()


@pytest.mark.usefixtures("mock_tempfile")
async def test_server_timeout_on_stop(
    mock_create_subprocess: MagicMock, server: Server
) -> None:
    """Test server run where the process takes too long to terminate."""
    # Start server thread
    await server.start()

    async def sleep() -> None:
        await asyncio.sleep(1)

    # Simulate timeout
    mock_create_subprocess.return_value.wait.side_effect = sleep

    with patch("homeassistant.components.go2rtc.server._TERMINATE_TIMEOUT", new=0.1):
        await server.stop()

    # Ensure terminate and kill were called due to timeout
    mock_create_subprocess.return_value.terminate.assert_called_once()
    mock_create_subprocess.return_value.kill.assert_called_once()


@pytest.mark.parametrize(
    "server_stdout",
    [
        [
            "09:00:03.466 INF go2rtc platform=linux/amd64 revision=780f378 version=1.9.5",
            "09:00:03.466 INF config path=/tmp/go2rtc.yaml",
        ]
    ],
)
@pytest.mark.usefixtures("mock_tempfile")
async def test_server_failed_to_start(
    mock_create_subprocess: MagicMock,
    server_stdout: list[str],
    server: Server,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test server, where an exception is raised if the expected log entry was not received until the timeout."""
    with (
        patch("homeassistant.components.go2rtc.server._SETUP_TIMEOUT", new=0.1),
        pytest.raises(HomeAssistantError, match="Go2rtc server didn't start correctly"),
    ):
        await server.start()

    # Verify go2rtc binary stdout was logged
    for entry in server_stdout:
        assert (
            "homeassistant.components.go2rtc.server",
            logging.DEBUG,
            entry,
        ) in caplog.record_tuples

    assert (
        "homeassistant.components.go2rtc.server",
        logging.ERROR,
        "Go2rtc server didn't start correctly",
    ) in caplog.record_tuples

    # Check that Popen was called with the right arguments
    mock_create_subprocess.assert_called_once_with(
        TEST_BINARY,
        "-c",
        "test.yaml",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        close_fds=False,
    )
