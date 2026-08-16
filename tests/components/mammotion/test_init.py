"""Tests for the Mammotion integration setup."""

import asyncio
from typing import Any
from unittest.mock import MagicMock, Mock

from aiohttp import ClientConnectorError
from freezegun.api import FrozenDateTimeFactory
from pymammotion.data.model.device import MowingDevice
from pymammotion.transport.base import AuthError, LoginFailedError
from Tea.exceptions import UnretryableException

from homeassistant.components.mammotion.const import DOMAIN
from homeassistant.components.mammotion.coordinator import DEFAULT_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_FINAL_WRITE
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import DEFAULT_NAME

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the config entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_mower_api.mammotion.stop.assert_awaited_once()
    mock_mower_api.mammotion.remove_device.assert_awaited_once_with(DEFAULT_NAME)


async def test_setup_retry_on_failed_refresh(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry is retried when the first data fetch fails."""
    mock_mower_api.update.return_value = None

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retry_on_connection_error(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry is retried when the cloud is unreachable."""
    mock_mower_api.mammotion.login_and_initiate_cloud.side_effect = (
        ClientConnectorError(Mock(), OSError("boom"))
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_state_restored_from_store(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Test the stored mower state is restored into the library on setup."""
    handle = Mock()
    mock_mower_api.mammotion.mower.return_value = handle
    storage_key = f"{DOMAIN}.{mock_config_entry.entry_id}"
    hass_storage[storage_key] = {
        "version": 1,
        "minor_version": 0,
        "key": storage_key,
        "data": {DEFAULT_NAME: MowingDevice().to_dict()},
    }

    await setup_integration(hass, mock_config_entry)

    handle.restore_device.assert_called_once()


async def test_state_persisted_on_final_write(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test mower state is not written on every poll but on Home Assistant stop."""
    await setup_integration(hass, mock_config_entry)
    storage_key = f"{DOMAIN}.{mock_config_entry.entry_id}"

    assert storage_key not in hass_storage

    freezer.tick(DEFAULT_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert storage_key not in hass_storage

    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
    await hass.async_block_till_done()

    assert DEFAULT_NAME in hass_storage[storage_key]["data"]


async def test_state_persisted_on_unload(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Test pending mower state is flushed when the entry is unloaded."""
    await setup_integration(hass, mock_config_entry)
    storage_key = f"{DOMAIN}.{mock_config_entry.entry_id}"

    assert storage_key not in hass_storage

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert DEFAULT_NAME in hass_storage[storage_key]["data"]


async def test_remove_entry_keeps_other_entry_state(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Test removing an entry leaves the stored state of other entries intact."""
    other_key = f"{DOMAIN}.other_entry_id"
    hass_storage[other_key] = {
        "version": 1,
        "minor_version": 0,
        "key": other_key,
        "data": {"Luba-OTHER": MowingDevice().to_dict()},
    }
    await setup_integration(hass, mock_config_entry)

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert f"{DOMAIN}.{mock_config_entry.entry_id}" not in hass_storage
    assert other_key in hass_storage


async def test_setup_error_on_unretryable_error(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry errors out on an unretryable login failure."""
    mock_mower_api.mammotion.login_and_initiate_cloud.side_effect = (
        UnretryableException(Mock(), OSError("boom"))
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_client_stopped_before_unload_returns(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the client is torn down before unload completes.

    A reload sets the entry up again as soon as unload returns.  If the old
    client is still holding its MQTT session, both sessions connect with the
    same client_id and the broker rejects them.
    """
    await setup_integration(hass, mock_config_entry)

    stopped = False

    async def _stop() -> None:
        # Suspend, as disconnecting a real MQTT transport does.
        await asyncio.sleep(0)
        nonlocal stopped
        stopped = True

    mock_mower_api.mammotion.stop.side_effect = _stop

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert stopped, "unload returned while the client still held its connection"


async def test_reload_does_not_overlap_clients(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a reload stops the old client before the new one logs in."""
    await setup_integration(hass, mock_config_entry)

    call_order: list[str] = []

    async def _stop() -> None:
        await asyncio.sleep(0)
        call_order.append("stop")

    async def _login(*args: Any, **kwargs: Any) -> None:
        call_order.append("login")

    mock_mower_api.mammotion.stop.side_effect = _stop
    mock_mower_api.mammotion.restore_credentials.side_effect = _login
    mock_mower_api.mammotion.login_and_initiate_cloud.side_effect = _login

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert call_order == ["stop", "login"]


async def test_login_failure_starts_reauth(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test stored credentials that no longer work prompt for reauth."""
    mock_mower_api.mammotion.login_and_initiate_cloud.side_effect = LoginFailedError(
        "user123", "bad password"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_auth_error_while_polling_starts_reauth(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an auth failure during a poll prompts for reauth."""
    await setup_integration(hass, mock_config_entry)

    mock_mower_api.update.side_effect = AuthError("user123", "token rejected")

    freezer.tick(DEFAULT_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
