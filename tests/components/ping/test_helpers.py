"""Test the exception handling in subprocess version of async_ping."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ping.helpers import PingDataSubProcess
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


class MockAsyncSubprocess:
    """Minimal mock of asyncio.subprocess.Process for testing."""

    def __init__(self, killsig=ProcessLookupError, **kwargs) -> None:
        """Store provided exception type for later."""
        self.killsig = killsig

    async def communicate(self) -> None:
        """Fails immediately with a timeout."""
        raise TimeoutError

    def kill(self) -> None:
        """Raise preset exception when called."""
        raise self.killsig


@pytest.mark.parametrize("exc", [TypeError, ProcessLookupError])
async def test_async_ping_expected_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    exc: Exception,
) -> None:
    """Test PingDataSubProcess.async_ping handles expected exceptions."""
    with patch(
        "asyncio.create_subprocess_exec", return_value=MockAsyncSubprocess(killsig=exc)
    ):
        # Actual parameters irrelevant, as subprocess will not be created
        ping = PingDataSubProcess(hass, host="10.10.10.10", count=3, privileged=False)
        assert await ping.async_ping() is None


async def test_async_ping_unexpected_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test PingDataSubProcess.async_ping does not suppress unexpected exceptions."""
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=MockAsyncSubprocess(killsig=KeyboardInterrupt),
    ):
        # Actual parameters irrelevant, as subprocess will not be created
        ping = PingDataSubProcess(hass, host="10.10.10.10", count=3, privileged=False)
        with pytest.raises(KeyboardInterrupt):
            assert await ping.async_ping() is None


class MockCompletedSubprocess:
    """Mock of asyncio.subprocess.Process that completes with output."""

    def __init__(self, stdout: bytes, stderr: bytes, returncode: int) -> None:
        """Store the output and return code."""
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        """Return the stored output."""
        return self._stdout, self._stderr


IPUTILS_OUTPUT = (
    b"PING 10.10.10.10 (10.10.10.10) 56(84) bytes of data.\n\n"
    b"--- 10.10.10.10 ping statistics ---\n"
    b"3 packets transmitted, 3 received, 0% packet loss, time 2003ms\n"
    b"rtt min/avg/max/mdev = 1.012/2.345/3.678/0.912 ms\n"
)
BUSYBOX_OUTPUT = (
    b"PING 10.10.10.10 (10.10.10.10): 56 data bytes\n\n"
    b"--- 10.10.10.10 ping statistics ---\n"
    b"3 packets transmitted, 3 packets received, 0% packet loss\n"
    b"round-trip min/avg/max = 1.012/2.345/3.678 ms\n"
)
UNREACHABLE_OUTPUT = (
    b"PING 10.10.10.10 (10.10.10.10) 56(84) bytes of data.\n\n"
    b"--- 10.10.10.10 ping statistics ---\n"
    b"3 packets transmitted, 0 received, 100% packet loss, time 2040ms\n"
)


@pytest.mark.parametrize(
    ("stdout", "returncode", "expected"),
    [
        pytest.param(
            IPUTILS_OUTPUT,
            0,
            {"min": "1.012", "avg": "2.345", "max": "3.678", "mdev": "0.912"},
            id="iputils",
        ),
        pytest.param(
            BUSYBOX_OUTPUT,
            0,
            {"min": "1.012", "avg": "2.345", "max": "3.678"},
            id="busybox",
        ),
        pytest.param(UNREACHABLE_OUTPUT, 1, None, id="unreachable"),
    ],
)
async def test_async_ping_subprocess_output(
    hass: HomeAssistant,
    stdout: bytes,
    returncode: int,
    expected: dict[str, str] | None,
) -> None:
    """Test PingDataSubProcess parses the ping binary output."""
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=MockCompletedSubprocess(stdout, b"", returncode),
    ):
        ping = PingDataSubProcess(hass, host="10.10.10.10", count=3, privileged=None)
        await ping.async_update()

    assert ping.data == expected
    assert ping.is_alive is (expected is not None)


async def test_async_ping_subprocess_command_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a ping binary failure is logged and reported as not alive."""
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=MockCompletedSubprocess(b"", b"ping: unknown host", 2),
    ):
        ping = PingDataSubProcess(hass, host="10.10.10.10", count=3, privileged=None)
        await ping.async_update()

    assert ping.data is None
    assert ping.is_alive is False
    assert "Error running command" in caplog.text
