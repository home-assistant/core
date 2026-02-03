"""Define tests for SimpliSafe setup."""

from unittest.mock import AsyncMock, patch

import pytest
from simplipy.errors import (
    EndpointUnavailableError,
    InvalidCredentialsError,
    RequestError,
    SimplipyError,
)

from homeassistant.components.simplisafe import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
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
        patch(
            "homeassistant.components.simplisafe.SimpliSafe._async_start_websocket_loop"
        ),
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
    """Test that exceptions propagate to the coordinator."""
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
