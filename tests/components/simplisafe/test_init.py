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
    ("exc", "expected_exception"),
    [
        (InvalidCredentialsError, ConfigEntryAuthFailed),
        (RequestError, UpdateFailed),
        (EndpointUnavailableError, None),
        (SimplipyError, UpdateFailed),
    ],
)
async def test_system_exceptions_via_coordinator(
    simplisafe_manager: SimpliSafe,
    exc: type[SimplipyError],
    expected_exception: type[HomeAssistantError],
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
