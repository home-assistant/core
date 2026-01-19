"""Define tests for SimpliSafe setup."""

from unittest.mock import AsyncMock, patch

from simplipy.errors import InvalidCredentialsError, RequestError, SimplipyError

from homeassistant.components.simplisafe import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
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


async def _trigger_requesterror_and_refresh(simpli) -> None:
    """Simulate RequestError on all systems and run coordinator refresh."""
    for system in simpli.systems.values():
        system.async_update = AsyncMock(side_effect=RequestError("Connection failed"))

    await simpli.coordinator.async_refresh()


async def test_requesterror_shuts_down_websocket(
    hass: HomeAssistant, setup_simplisafe_integration, config_entry
) -> None:
    """RequestError cancels the websocket task."""
    simpli = hass.data[DOMAIN][config_entry.entry_id]
    await _trigger_requesterror_and_refresh(simpli)
    # Websocket task should be cancelled
    assert simpli._websocket_reconnect_task is None


async def test_websocket_restarts_after_successful_update(
    hass: HomeAssistant, setup_simplisafe_integration, config_entry
) -> None:
    """Websocket loop is restarted after successful update."""
    simpli = hass.data[DOMAIN][config_entry.entry_id]
    # First, simulate failure to stop websocket
    await _trigger_requesterror_and_refresh(simpli)
    assert simpli._websocket_reconnect_task is None

    # Then patch systems to succeed
    for system in simpli.systems.values():
        system.async_update = AsyncMock(return_value=None)

    await simpli.coordinator.async_refresh()
    assert simpli._websocket_reconnect_task is not None


async def test_invalid_credentials_raises_configentryauthfailed(
    hass: HomeAssistant, setup_simplisafe_integration, config_entry
) -> None:
    """InvalidCredentialsError triggers ConfigEntryAuthFailed."""
    simpli = hass.data[DOMAIN][config_entry.entry_id]

    for system in simpli.systems.values():
        system.async_update = AsyncMock(
            side_effect=InvalidCredentialsError("Bad token")
        )
    await simpli.coordinator.async_refresh()
    assert isinstance(simpli.coordinator.last_exception, ConfigEntryAuthFailed)


async def test_simplipyerror_propagates(
    hass: HomeAssistant, setup_simplisafe_integration, config_entry
) -> None:
    """Other SimplipyError exceptions raise UpdateFailed."""
    simpli = hass.data[DOMAIN][config_entry.entry_id]

    for system in simpli.systems.values():
        system.async_update = AsyncMock(side_effect=SimplipyError("Some error"))

    await simpli.coordinator.async_refresh()
    assert isinstance(simpli.coordinator.last_exception, UpdateFailed)
