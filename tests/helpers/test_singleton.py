"""Test singleton helper."""

import asyncio
from typing import Any
from unittest.mock import Mock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import singleton


@pytest.fixture
def mock_hass():
    """Mock hass fixture."""
    return Mock(data={})


@pytest.mark.parametrize("result", [object(), {}, []])
async def test_singleton_async(mock_hass: HomeAssistant, result: Any) -> None:
    """Test singleton with async function."""

    @singleton.singleton("test_key")
    async def something(hass: HomeAssistant) -> Any:
        return result

    result1 = await something(mock_hass)
    result2 = await something(mock_hass)
    assert result1 is result
    assert result1 is result2
    assert "test_key" in mock_hass.data
    assert mock_hass.data["test_key"] is result1


@pytest.mark.parametrize("result", [object(), {}, []])
def test_singleton(mock_hass: HomeAssistant, result: Any) -> None:
    """Test singleton with function."""

    @singleton.singleton("test_key")
    def something(hass: HomeAssistant) -> Any:
        return result

    result1 = something(mock_hass)
    result2 = something(mock_hass)
    assert result1 is result
    assert result1 is result2
    assert "test_key" in mock_hass.data
    assert mock_hass.data["test_key"] is result1


async def test_singleton_async_raises(mock_hass: HomeAssistant) -> None:
    """Test the key is not poisoned when the wrapped coroutine raises."""
    calls = 0

    @singleton.singleton("test_key")
    async def something(hass: HomeAssistant) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("boom")
        return "result"

    with pytest.raises(ValueError, match="boom"):
        await something(mock_hass)

    # The failure cleared the key, so a later call retries cleanly.
    assert "test_key" not in mock_hass.data

    assert await something(mock_hass) == "result"
    assert mock_hass.data["test_key"] == "result"
    assert calls == 2


async def test_singleton_async_concurrent_raises(mock_hass: HomeAssistant) -> None:
    """Test a concurrent caller wakes up when the in-flight call raises."""
    release = asyncio.Event()
    calls = 0

    @singleton.singleton("test_key")
    async def something(hass: HomeAssistant) -> Any:
        nonlocal calls
        calls += 1
        await release.wait()
        raise ValueError("boom")

    # First caller installs the future and parks on release.wait().
    task1 = asyncio.create_task(something(mock_hass))
    await asyncio.sleep(0)
    # Second caller finds the in-flight future and waits on it.
    task2 = asyncio.create_task(something(mock_hass))
    await asyncio.sleep(0)

    release.set()

    async with asyncio.timeout(1):
        with pytest.raises(ValueError, match="boom"):
            await task1
        with pytest.raises(ValueError, match="boom"):
            await task2

    # Only the first caller ran the wrapped function; the waiter observed its error.
    assert calls == 1
    assert "test_key" not in mock_hass.data
