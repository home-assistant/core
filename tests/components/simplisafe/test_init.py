"""Define tests for SimpliSafe setup."""

import asyncio
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
import simplipy.errors

from homeassistant.components.simplisafe import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SimpliSafe,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("patch_simplisafe_api")
async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


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
    ("exc", "expected", "cancel_websocket"),
    [
        (simplipy.errors.InvalidCredentialsError, ConfigEntryAuthFailed, True),
        (simplipy.errors.RequestError, UpdateFailed, True),
        (simplipy.errors.EndpointUnavailableError, None, False),
        (simplipy.errors.SimplipyError, UpdateFailed, False),
    ],
)
async def test_coordinator_exceptions_propagate(
    hass: HomeAssistant,
    simplisafe_manager: SimpliSafe,
    freezer: FrozenDateTimeFactory,
    exc: simplipy.errors.SimplipyError,
    expected: type[Exception] | None,
    cancel_websocket: bool,
) -> None:
    """Test that SimpliSafe exceptions propagate correctly."""
    manager = simplisafe_manager

    # Patch all systems to raise the exception
    for system in manager.systems.values():
        system.async_update = AsyncMock(side_effect=exc("fail"))

    # Capture the websocket task before the update
    task_before = manager._websocket_task
    assert task_before is not None

    # Advance time to trigger the coordinator update
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await asyncio.sleep(0)

    # Verify websocket task state
    if cancel_websocket:
        task = manager._websocket_task
        assert task is None or task.cancelled() or task.done()
    else:
        task = manager._websocket_task
        assert task is task_before
        assert not task.done()

    # --- CLEANUP via config entry unload ---
    await hass.config_entries.async_unload(manager.entry.entry_id)
    await hass.async_block_till_done()

    # Websocket task should now be fully cancelled
    assert manager._websocket_reconnect_task is None
