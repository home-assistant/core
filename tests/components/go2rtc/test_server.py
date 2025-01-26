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
def enable_ui() -> bool:
    """Fixture to enable the UI."""
    return False


@pytest.fixture
def server(hass: HomeAssistant, enable_ui: bool) -> Server:
    """Fixture to initialize the Server."""
    return Server(hass, binary=TEST_BINARY, enable_ui=enable_ui)


@pytest.fixture
def mock_tempfile() -> Generator[Mock]:
    """Fixture to mock NamedTemporaryFile."""
    with patch(
        "homeassistant.components.go2rtc.server.NamedTemporaryFile", autospec=True
    ) as mock_tempfile:
        file = mock_tempfile.return_value.__enter__.return_value
        file.name = "test.yaml"
        yield file


def _assert_server_output_logged(
    server_stdout: list[str],
    caplog: pytest.LogCaptureFixture,
    loglevel: int,
    expect_logged: bool,
) -> None:
    """Check server stdout was logged."""
    for entry in server_stdout:
        assert (
            (
                "homeassistant.components.go2rtc.server",
                loglevel,
                entry,
            )
            in caplog.record_tuples
        ) is expect_logged


def assert_server_output_logged(
    server_stdout: list[str],
    caplog: pytest.LogCaptureFixture,
    loglevel: int,
) -> None:
    """Check server stdout was logged."""
    _assert_server_output_logged(server_stdout, caplog, loglevel, True)


def assert_server_output_not_logged(
    server_stdout: list[str],
    caplog: pytest.LogCaptureFixture,
    loglevel: int,
) -> None:
    """Check server stdout was logged."""
    _assert_server_output_logged(server_stdout, caplog, loglevel, False)


@pytest.mark.parametrize(
    ("enable_ui", "api_ip"),
    [
        (True, ""),
        (False, "127.0.0.1"),
    ],
)
async def test_server_run_success(
    mock_create_subprocess: AsyncMock,
    rest_client: AsyncMock,
    server_stdout: list[str],
    server: Server,
    caplog: pytest.LogCaptureFixture,
    mock_tempfile: Mock,
    api_ip: str,
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
    mock_tempfile.write.assert_called_once_with(
        f"""# This file is managed by Home Assistant
# Do not edit it manually

api:
  listen: "{api_ip}:11984"

rtsp:
  listen: "127.0.0.1:18554"

webrtc:
  listen: ":18555/tcp"
  ice_servers: []
""".encode()
    )

    # Verify go2rtc binary stdout was logged with debug level
    assert_server_output_logged(server_stdout, caplog, logging.DEBUG)

    await server.stop()
    mock_create_subprocess.return_value.terminate.assert_called_once()

    # Verify go2rtc binary stdout was not logged with warning level
    assert_server_output_not_logged(server_stdout, caplog, logging.WARNING)


@pytest.mark.usefixtures("mock_tempfile")
async def test_server_timeout_on_stop(
    mock_create_subprocess: MagicMock, rest_client: AsyncMock, server: Server
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

    # Verify go2rtc binary stdout was logged with debug and warning level
    assert_server_output_logged(server_stdout, caplog, logging.DEBUG)
    assert_server_output_logged(server_stdout, caplog, logging.WARNING)

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


@pytest.mark.parametrize(
    ("server_stdout", "expected_loglevel"),
    [
        (
            [
                "09:00:03.466 TRC [api] register path path=/",
                "09:00:03.466 DBG build vcs.time=2024-10-28T19:47:55Z version=go1.23.2",
                "09:00:03.466 INF go2rtc platform=linux/amd64 revision=780f378 version=1.9.5",
                "09:00:03.467 INF [api] listen addr=127.0.0.1:1984",
                "09:00:03.466 WRN warning message",
                '09:00:03.466 ERR [api] listen error="listen tcp 127.0.0.1:11984: bind: address already in use"',
                "09:00:03.466 FTL fatal message",
                "09:00:03.466 PNC panic message",
                "exit with signal: interrupt",  # Example of stderr write
            ],
            [
                logging.DEBUG,
                logging.DEBUG,
                logging.DEBUG,
                logging.DEBUG,
                logging.WARNING,
                logging.WARNING,
                logging.ERROR,
                logging.ERROR,
                logging.WARNING,
            ],
        )
    ],
)
@patch("homeassistant.components.go2rtc.server._RESPAWN_COOLDOWN", 0)
async def test_log_level_mapping(
    hass: HomeAssistant,
    mock_create_subprocess: MagicMock,
    server_stdout: list[str],
    rest_client: AsyncMock,
    server: Server,
    caplog: pytest.LogCaptureFixture,
    expected_loglevel: list[int],
) -> None:
    """Log level mapping."""
    evt = asyncio.Event()

    async def wait_event() -> None:
        await evt.wait()

    mock_create_subprocess.return_value.wait.side_effect = wait_event

    await server.start()

    await asyncio.sleep(0.1)
    await hass.async_block_till_done()

    # Verify go2rtc binary stdout was logged with default level
    for i, entry in enumerate(server_stdout):
        assert (
            "homeassistant.components.go2rtc.server",
            expected_loglevel[i],
            entry,
        ) in caplog.record_tuples

    evt.set()
    await asyncio.sleep(0.1)
    await hass.async_block_till_done()

    assert_server_output_logged(server_stdout, caplog, logging.WARNING)

    await server.stop()


@patch("homeassistant.components.go2rtc.server._RESPAWN_COOLDOWN", 0)
async def test_server_restart_process_exit(
    hass: HomeAssistant,
    mock_create_subprocess: AsyncMock,
    server_stdout: list[str],
    rest_client: AsyncMock,
    server: Server,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the server is restarted when it exits."""
    evt = asyncio.Event()

    async def wait_event() -> None:
        await evt.wait()

    mock_create_subprocess.return_value.wait.side_effect = wait_event

    await server.start()
    mock_create_subprocess.assert_awaited_once()
    mock_create_subprocess.reset_mock()

    await asyncio.sleep(0.1)
    await hass.async_block_till_done()
    mock_create_subprocess.assert_not_awaited()

    # Verify go2rtc binary stdout was not yet logged with warning level
    assert_server_output_not_logged(server_stdout, caplog, logging.WARNING)

    evt.set()
    await asyncio.sleep(0.1)
    mock_create_subprocess.assert_awaited_once()

    # Verify go2rtc binary stdout was logged with warning level
    assert_server_output_logged(server_stdout, caplog, logging.WARNING)

    await server.stop()


@patch("homeassistant.components.go2rtc.server._RESPAWN_COOLDOWN", 0)
async def test_server_restart_process_error(
    hass: HomeAssistant,
    mock_create_subprocess: AsyncMock,
    server_stdout: list[str],
    rest_client: AsyncMock,
    server: Server,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the server is restarted on error."""
    mock_create_subprocess.return_value.wait.side_effect = [Exception, None, None, None]

    await server.start()
    mock_create_subprocess.assert_awaited_once()
    mock_create_subprocess.reset_mock()

    # Verify go2rtc binary stdout was not yet logged with warning level
    assert_server_output_not_logged(server_stdout, caplog, logging.WARNING)

    await asyncio.sleep(0.1)
    await hass.async_block_till_done()
    mock_create_subprocess.assert_awaited_once()

    # Verify go2rtc binary stdout was logged with warning level
    assert_server_output_logged(server_stdout, caplog, logging.WARNING)

    await server.stop()


@patch("homeassistant.components.go2rtc.server._RESPAWN_COOLDOWN", 0)
async def test_server_restart_api_error(
    hass: HomeAssistant,
    mock_create_subprocess: AsyncMock,
    server_stdout: list[str],
    rest_client: AsyncMock,
    server: Server,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the server is restarted on error."""
    rest_client.streams.list.side_effect = Exception

    await server.start()
    mock_create_subprocess.assert_awaited_once()
    mock_create_subprocess.reset_mock()

    # Verify go2rtc binary stdout was not yet logged with warning level
    assert_server_output_not_logged(server_stdout, caplog, logging.WARNING)

    await asyncio.sleep(0.1)
    await hass.async_block_till_done()
    mock_create_subprocess.assert_awaited_once()

    # Verify go2rtc binary stdout was logged with warning level
    assert_server_output_logged(server_stdout, caplog, logging.WARNING)

    await server.stop()


@patch("homeassistant.components.go2rtc.server._RESPAWN_COOLDOWN", 0)
async def test_server_restart_error(
    hass: HomeAssistant,
    mock_create_subprocess: AsyncMock,
    server_stdout: list[str],
    rest_client: AsyncMock,
    server: Server,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling when exception is raised during restart."""
    rest_client.streams.list.side_effect = Exception
    mock_create_subprocess.return_value.terminate.side_effect = [Exception, None]

    await server.start()
    mock_create_subprocess.assert_awaited_once()
    mock_create_subprocess.reset_mock()

    # Verify go2rtc binary stdout was not yet logged with warning level
    assert_server_output_not_logged(server_stdout, caplog, logging.WARNING)

    await asyncio.sleep(0.1)
    await hass.async_block_till_done()
    mock_create_subprocess.assert_awaited_once()

    # Verify go2rtc binary stdout was logged with warning level
    assert_server_output_logged(server_stdout, caplog, logging.WARNING)

    assert "Unexpected error when restarting go2rtc server" in caplog.text

    await server.stop()
