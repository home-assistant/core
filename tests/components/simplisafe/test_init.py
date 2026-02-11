"""Define tests for SimpliSafe setup."""

import asyncio
import contextlib
from unittest.mock import AsyncMock, patch

import pytest
from simplipy.errors import (
    EndpointUnavailableError,
    InvalidCredentialsError,
    RequestError,
    SimplipyError,
    WebsocketError,
)

from homeassistant.components.simplisafe import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    WEBSOCKET_RECONNECT_RETRIES,
    WEBSOCKET_RETRY_DELAY,
    SimpliSafe,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.setup import async_setup_component


async def test_base_station_migration(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, api, config, config_entry
) -> None:
    """Test that errors are shown when duplicates are added."""
    old_identifers = (DOMAIN, 12345)
    new_identifiers = (DOMAIN, "12345")

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={old_identifers},
        manufacturer="SimpliSafe",
        name="old",
    )

    with (
        patch(
            "homeassistant.components.simplisafe.config_flow.API.async_from_auth",
            return_value=api,
        ),
        patch(
            "homeassistant.components.simplisafe.API.async_from_auth",
            return_value=api,
        ),
        patch(
            "homeassistant.components.simplisafe.API.async_from_refresh_token",
            return_value=api,
        ),
        patch("homeassistant.components.simplisafe.SimpliSafe._async_websocket_loop"),
        patch(
            "homeassistant.components.simplisafe.PLATFORMS",
            [],
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    assert device_registry.async_get_device(identifiers={old_identifers}) is None
    assert device_registry.async_get_device(identifiers={new_identifiers}) is not None


@pytest.mark.parametrize(
    ("exc", "expected_exception", "should_cancel_task"),
    [
        (InvalidCredentialsError, ConfigEntryAuthFailed, True),
        (RequestError, UpdateFailed, True),
        (EndpointUnavailableError, None, False),
        (SimplipyError, UpdateFailed, False),
    ],
)
async def test_coordinator_exceptions_and_websocket_behavior(
    simplisafe_manager: SimpliSafe,
    exc: type[SimplipyError],
    expected_exception: type[HomeAssistantError],
    should_cancel_task: bool,
) -> None:
    """Test that exceptions propagate to the coordinator and successfully stop and restart the websocket task."""

    manager: SimpliSafe = simplisafe_manager
    coordinator = manager.coordinator
    assert coordinator is not None

    async def raise_exc(*args, **kwargs) -> None:
        raise exc("fail")

    for system in manager.systems.values():
        system.async_update = AsyncMock(side_effect=raise_exc)

    # Advance time to trigger coordinator update
    assert coordinator.update_interval is not None
    assert coordinator.update_interval == DEFAULT_SCAN_INTERVAL
    await coordinator.async_refresh()
    await manager._hass.async_block_till_done()

    # Verify coordinator recorded the exception correctly
    if expected_exception is None:
        assert coordinator.last_update_success
        assert coordinator.last_exception is None
    else:
        assert not coordinator.last_update_success
        assert isinstance(coordinator.last_exception, expected_exception)

    task_after = manager._websocket_task
    if should_cancel_task:
        assert task_after is None or task_after.done() or task_after.cancelled()
    else:
        assert task_after is not None and not task_after.done()

    if should_cancel_task:
        # Save the task before we patch async_update to succeed
        task_before_restart = manager._websocket_task

        # Patch async_update to succeed for the next refresh
        async def succeed_update(*args, **kwargs):
            return None

        for system in manager.systems.values():
            system.async_update = AsyncMock(side_effect=succeed_update)

        # Trigger the next successful coordinator refresh
        await coordinator.async_refresh()
        await manager._hass.async_block_till_done()

        # Check that the websocket has restarted
        task_after_restart = manager._websocket_task
        assert task_after_restart is not None
        assert task_after_restart is not task_before_restart
        assert not task_after_restart.done()
    else:
        # For exceptions that don’t cancel the websocket, just assert it’s still running
        assert task_after is not None and not task_after.done()


@pytest.mark.parametrize(
    ("exc_type", "max_retries"),
    [
        (WebsocketError, WEBSOCKET_RECONNECT_RETRIES),
        (asyncio.CancelledError, 1),
        (Exception, 1),
    ],
)
async def test_websocket_backoff_parametrized(
    simplisafe_manager: SimpliSafe, websocket, exc_type, max_retries
) -> None:
    """Test websocket backoff behavior."""
    manager = simplisafe_manager
    sleep_calls: list[float] = []

    original_sleep = asyncio.sleep

    async def fake_sleep(delay: float):
        if delay >= WEBSOCKET_RETRY_DELAY:
            sleep_calls.append(delay)
        await original_sleep(0)

    with patch("asyncio.sleep", new=fake_sleep):
        task = manager._websocket_task
        assert task is not None

        if exc_type is asyncio.CancelledError:
            task.cancel()
            await asyncio.sleep(0)  # yield
        elif exc_type is Exception:
            # Generic exception: trigger once and yield
            websocket.state["raise_exc"] = exc_type("fail")
            websocket.listen_event.set()
            await asyncio.sleep(0)
        else:
            # Test retries 1..max_retries automatically
            for retries in range(1, max_retries + 1):
                # trigger websocket error 'retries' times
                for i in range(retries):
                    websocket.state["raise_exc"] = exc_type(f"fail {i}")
                    websocket.listen_event.set()
                    # wait until the websocket task has incremented retries and slept
                    while len(sleep_calls) < i + 1:
                        await asyncio.sleep(0.01)

                # clear exception → recovery
                websocket.state["raise_exc"] = None
                websocket.listen_event.set()
                await asyncio.sleep(0.01)

                # verify the prefix of expected backoff
                expected_backoff = [
                    WEBSOCKET_RETRY_DELAY * (2**i) for i in range(retries)
                ]
                assert sleep_calls[-retries:] == expected_backoff, (
                    f"Backoff for {retries} retries should be {expected_backoff}, got {sleep_calls[-retries:]}"
                )

    # --- Verify task state ---
    task = manager._websocket_task
    if exc_type is asyncio.CancelledError or exc_type is Exception:
        assert task is None or task.done() or task.cancelled()
    elif retries < WEBSOCKET_RECONNECT_RETRIES:
        assert task is not None
        assert not task.done()
    else:
        assert task is None or task.done()

    # --- Cleanup ---
    if task and not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
