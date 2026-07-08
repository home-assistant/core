"""Tests for integration setup and unload."""

from unittest.mock import AsyncMock, Mock, patch

from besen.exceptions import CannotConnect, InvalidAuth

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test setup creates runtime data and forwards the switch platform."""

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id) is True
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_besen_client.async_start.assert_awaited_once()
    assert hass.states.get("switch.garage_charge") is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id) is True
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_besen_client.add_listener.return_value.assert_called_once_with()
    mock_besen_client.async_stop.assert_awaited_once()


async def test_setup_entry_no_connectable_path(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    mock_ble_device: Mock,
) -> None:
    """Test setup retries when no active Bluetooth path exists."""

    mock_ble_device.return_value = None
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_besen_client.async_start.assert_not_awaited()


async def test_setup_entry_auth_error_fails_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test setup maps invalid auth to a config-entry auth failure."""

    mock_besen_client.async_start.side_effect = InvalidAuth("bad pin")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_besen_client.add_listener.return_value.assert_called_once_with()
    mock_besen_client.async_stop.assert_awaited_once()


async def test_setup_entry_connect_error_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test setup maps connection errors to a retry."""

    mock_besen_client.async_start.side_effect = CannotConnect("offline")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_besen_client.add_listener.return_value.assert_called_once_with()
    mock_besen_client.async_stop.assert_awaited_once()


async def test_unload_skips_shutdown_when_platform_unload_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test unload does not stop the client when platform unload fails."""

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id) is True
    await hass.async_block_till_done()

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=False),
    ):
        assert (
            await hass.config_entries.async_unload(mock_config_entry.entry_id) is False
        )

    mock_besen_client.add_listener.return_value.assert_not_called()
    mock_besen_client.async_stop.assert_not_awaited()
