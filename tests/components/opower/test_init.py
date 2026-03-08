"""Tests for the Opower integration."""

from unittest.mock import AsyncMock

from opower.exceptions import ApiException, CannotConnect, InvalidAuth
import pytest

from homeassistant.components.opower.const import DOMAIN
from homeassistant.components.recorder import Recorder
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_setup_unload_entry(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test successful setup and unload of a config entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_opower_api.async_login.assert_awaited_once()
    mock_opower_api.async_get_forecast.assert_awaited_once()
    mock_opower_api.async_get_accounts.assert_awaited_once()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


@pytest.mark.parametrize(
    ("login_side_effect", "expected_state"),
    [
        (
            CannotConnect(),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            InvalidAuth(),
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
)
async def test_login_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
    login_side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test for login error."""
    mock_opower_api.async_login.side_effect = login_side_effect

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_get_forecast_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test for API error when getting forecast."""
    mock_opower_api.async_get_forecast.side_effect = ApiException(
        message="forecast error", url=""
    )

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_get_accounts_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test for API error when getting accounts."""
    mock_opower_api.async_get_accounts.side_effect = ApiException(
        message="accounts error", url=""
    )

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_get_cost_reads_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test for API error when getting cost reads."""
    mock_opower_api.async_get_cost_reads.side_effect = ApiException(
        message="cost reads error", url=""
    )

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_remove_config_entry_device(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test manually removing a device."""
    # We must set up the config component for the device registry websocket to work
    assert await async_setup_component(hass, "config", {})

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # 1. Test removing an active device (should fail)
    active_devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(active_devices) > 0
    active_device = active_devices[0]

    ws_client = await hass_ws_client(hass)
    response = await ws_client.remove_device(
        active_device.id, mock_config_entry.entry_id
    )
    assert response["success"] is False

    # 2. Test removing a stale device (should succeed)
    # Create a stale device that is not in coordinator.data and has no entities
    stale_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "pge_stale_account_12345")},
    )

    response = await ws_client.remove_device(
        stale_device.id, mock_config_entry.entry_id
    )

    assert response["success"] is True
    # Verify the device is actually gone from the registry
    assert device_registry.async_get(stale_device.id) is None
