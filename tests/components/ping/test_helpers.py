"""Test the exception handling in subprocess version of async_ping."""

from unittest.mock import patch

import pytest

from homeassistant.components.ping.helpers import PingDataSubProcess
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


class MockAsyncSubprocess:
    """Minimal mock implementation of asyncio.subprocess.Process for exception testing."""

    def __init__(self, killsig=ProcessLookupError, **kwargs) -> None:
        """Store provided exception type for later."""
        self.killsig = killsig

    async def communicate(self) -> None:
        """Fails immediately with a timeout."""
        raise TimeoutError

    async def kill(self) -> None:
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
