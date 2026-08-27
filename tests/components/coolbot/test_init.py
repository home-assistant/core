"""Setup, unload, and device-removal behavior."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from pycoolbot import CoolbotAuthError, CoolbotError

from homeassistant.components.coolbot import async_remove_config_entry_device
from homeassistant.components.coolbot.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_and_unload(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """The entry loads, exposes runtime data, and closes its socket on unload."""
    assert await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_client.async_close.assert_awaited()


async def test_setup_retries_when_service_is_unreachable(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A connection failure at setup schedules a retry, not a hard error.

    The failed client is closed rather than leaked: a rejected connect still
    leaves its socket and reader task running until someone closes it.
    """
    mock_client.async_connect.side_effect = CoolbotError("down")

    assert not await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_client.async_close.assert_awaited()


async def test_an_aborted_first_refresh_closes_the_socket(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """When setup fails after connecting, nothing else can close the socket.

    An unexpected error is the case that matters: the library's own errors are
    already closed by the refresh itself, but runtime_data is never assigned,
    so an unhandled one would otherwise leave the connection open for good.
    """
    mock_client.async_get_devices.side_effect = RuntimeError("surprise")

    assert not await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_client.async_close.assert_awaited()


async def test_setup_succeeds_for_an_account_with_no_devices(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """An account reporting no coolers loads rather than retrying forever."""
    mock_client.async_get_devices.return_value = []

    assert await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.data == {}


async def test_the_last_cooler_can_be_deleted_once_the_account_drops_it(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Removal is refused while reported, and allowed once it is gone."""
    assert await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "coolbot_aabbccddeeff"), mock_config_entry.entry_id
    )
    assert device is not None
    assert not await async_remove_config_entry_device(hass, mock_config_entry, device)

    mock_client.async_get_devices.return_value = []
    async_fire_time_changed(
        hass, dt_util.utcnow() + UPDATE_INTERVAL + timedelta(seconds=1)
    )
    await hass.async_block_till_done()

    assert await async_remove_config_entry_device(hass, mock_config_entry, device)


async def test_setup_starts_reauth_on_bad_credentials(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Rejected credentials at setup prompt for reauth instead of retrying."""
    mock_client.async_connect.side_effect = CoolbotAuthError("rejected")

    assert not await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(flow["context"]["source"] == "reauth" for flow in flows)


async def test_removing_a_device_the_account_still_reports_is_refused(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A device the account still reports would just be recreated."""
    assert await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "coolbot_aabbccddeeff"), mock_config_entry.entry_id
    )
    assert device is not None
    assert not await async_remove_config_entry_device(hass, mock_config_entry, device)


async def test_removing_a_vanished_device_is_allowed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A device the account no longer reports may be deleted."""
    assert await setup_integration(hass, mock_config_entry)

    orphan = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "coolbot_gone")},
    )
    assert await async_remove_config_entry_device(hass, mock_config_entry, orphan)
