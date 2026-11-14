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
    """Mock of asyncio.subprocess.Process that finishes with given output."""

    def __init__(self, stdout: bytes, stderr: bytes, returncode: int) -> None:
        """Store the output to return."""
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        """Return the stored output."""
        return self._stdout, self._stderr


@pytest.mark.parametrize(
    ("stdout", "returncode"),
    [
        pytest.param(
            b"PING 10.10.10.10 (10.10.10.10) 56(84) bytes of data.\n\n"
            b"--- 10.10.10.10 ping statistics ---\n"
            b"3 packets transmitted, 0 received, 100% packet loss, time 2040ms\n",
            1,
            id="linux",
        ),
        pytest.param(
            b"PING 10.10.10.10 (10.10.10.10): 56 data bytes\n\n"
            b"--- 10.10.10.10 ping statistics ---\n"
            b"3 packets transmitted, 0 packets received, 100.0% packet loss\n",
            2,
            id="macos",
        ),
        pytest.param(
            b"PING 10.10.10.10 (10.10.10.10): 56 data bytes\n\n"
            b"--- 10.10.10.10 ping statistics ---\n"
            b"3 packets transmitted, 0 packets received, 100% packet loss\n",
            1,
            id="busybox",
        ),
    ],
)
async def test_async_update_no_replies(
    hass: HomeAssistant, stdout: bytes, returncode: int
) -> None:
    """Test a resolvable host without replies reports 100% packet loss."""
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=MockCompletedSubprocess(stdout, b"", returncode),
    ):
        ping = PingDataSubProcess(hass, host="10.10.10.10", count=3, privileged=False)
        await ping.async_update()

    assert ping.is_alive is False
    assert ping.data == {"loss": 100.0}


@pytest.mark.parametrize(
    ("stderr", "returncode"),
    [
        pytest.param(
            b"ping: nohost.invalid: Name or service not known\n", 2, id="linux"
        ),
        pytest.param(
            b"ping: cannot resolve nohost.invalid: Unknown host\n", 68, id="macos"
        ),
        pytest.param(b"ping: bad address 'nohost.invalid'\n", 1, id="busybox"),
    ],
)
async def test_async_update_name_not_resolved(
    hass: HomeAssistant, stderr: bytes, returncode: int
) -> None:
    """Test an unresolvable host clears stale data and reports no measurement."""
    ping = PingDataSubProcess(hass, host="nohost.invalid", count=3, privileged=False)
    ping.data = {"min": "1.0", "avg": "1.0", "max": "1.0", "loss": 0.0}
    ping.is_alive = True
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=MockCompletedSubprocess(b"", stderr, returncode),
    ):
        await ping.async_update()

    assert ping.is_alive is False
    assert ping.data is None


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        pytest.param(
            b"--- 10.10.10.10 ping statistics ---\n"
            b"3 packets transmitted, 2 received, 33.3333% packet loss, time 2003ms\n"
            b"rtt min/avg/max/mdev = 1.100/1.200/1.300/0.100 ms\n",
            {
                "min": "1.100",
                "avg": "1.200",
                "max": "1.300",
                "mdev": "0.100",
                "loss": 33.3333,
            },
            id="linux",
        ),
        pytest.param(
            b"--- 10.10.10.10 ping statistics ---\n"
            b"3 packets transmitted, 3 packets received, 0% packet loss\n"
            b"round-trip min/avg/max = 1.100/1.200/1.300 ms\n",
            {"min": "1.100", "avg": "1.200", "max": "1.300", "loss": 0.0},
            id="busybox",
        ),
    ],
)
async def test_async_update_replies(
    hass: HomeAssistant, stdout: bytes, expected: dict[str, str | float]
) -> None:
    """Test a reachable host reports round trip times and packet loss."""
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=MockCompletedSubprocess(stdout, b"", 0),
    ):
        ping = PingDataSubProcess(hass, host="10.10.10.10", count=3, privileged=False)
        await ping.async_update()

    assert ping.is_alive is True
    assert ping.data == expected


async def test_async_ping_subprocess_uses_c_locale(hass: HomeAssistant) -> None:
    """Test the ping binary runs in the C locale so its output can be parsed."""
    ping = PingDataSubProcess(hass, host="10.10.10.10", count=3, privileged=False)
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=MockCompletedSubprocess(b"", b"", 1),
    ) as mock_exec:
        await ping.async_update()

    assert mock_exec.call_args.kwargs["env"]["LC_ALL"] == "C"


async def test_async_ping_subprocess_unparsable_round_trip(hass: HomeAssistant) -> None:
    """Test output with packet statistics but an unparsable round trip line."""
    ping = PingDataSubProcess(hass, host="10.10.10.10", count=3, privileged=False)
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=MockCompletedSubprocess(
            b"3 packets transmitted, 3 received, 0% packet loss\nrtt min/avg/max/mdev = garbled\n",
            b"",
            0,
        ),
    ):
        await ping.async_update()

    assert ping.is_alive is False
    assert ping.data is None
